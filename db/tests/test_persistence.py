"""Integration tests: set TEST_DATABASE_URL to a disposable PostgreSQL database."""

import os
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4


class PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = os.environ.get("TEST_DATABASE_URL")
        if not base:
            raise unittest.SkipTest("TEST_DATABASE_URL is required")
        try:
            import psycopg
            from psycopg.conninfo import make_conninfo
        except ImportError as exc:
            raise unittest.SkipTest("install db/requirements.txt") from exc
        cls.psycopg = psycopg
        cls.schema = "ec_test_" + uuid4().hex
        with psycopg.connect(base, autocommit=True) as conn:
            conn.execute(f"create schema {cls.schema}")
        cls.url = make_conninfo(base, options=f"-c search_path={cls.schema}")
        from db.migrate import migrate
        cls.applied = migrate(cls.url)
        cls.applied_again = migrate(cls.url)

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "schema"):
            return
        with cls.psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True) as conn:
            conn.execute(f"drop schema {cls.schema} cascade")

    def setUp(self):
        self.pilot, self.client, self.leader, self.worker = [uuid4() for _ in range(4)]
        self.material, self.reward, self.request, self.slot = [uuid4() for _ in range(4)]
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute("insert into pilots (id,name,city) values (%s,%s,'Barranquilla')",
                         (self.pilot, str(self.pilot)))
            conn.execute("""insert into users
                (id,pilot_id,email,document_number,full_name,role,password_hash)
                values (%s,%s,%s,%s,'Cliente ficticio','cliente','TEST_ONLY')""",
                (self.client, self.pilot, f"{self.client}@example.invalid", "1" + str(self.client.int)[:15]))
            conn.execute("""insert into users
                (id,pilot_id,email,full_name,role,password_hash)
                values (%s,%s,%s,'Líder ficticia','lider','TEST_ONLY')""",
                (self.leader, self.pilot, f"{self.leader}@example.invalid"))
            conn.execute("insert into field_workers (id,pilot_id,full_name) values (%s,%s,'Equipo ficticio')",
                         (self.worker, self.pilot))
            conn.execute("insert into materials (id,code,name) values (%s,%s,'PET')",
                         (self.material, str(self.material)))
            conn.execute("""insert into point_rules (material_id,points_per_kg,valid_from)
                values (%s,10,'2020-01-01T00:00:00Z')""", (self.material,))
            conn.execute("""insert into rewards (id,pilot_id,code,name,points_cost,stock)
                values (%s,%s,%s,'Premio ficticio',20,2)""",
                (self.reward, self.pilot, str(self.reward)))
            conn.execute("""insert into pickup_requests
                (id,client_id,pilot_id,address,status)
                values (%s,%s,%s,'Dirección ficticia','programada')""",
                (self.request, self.client, self.pilot))
            conn.execute("""insert into pickup_slots (id,pilot_id,starts_at,ends_at)
                values (%s,%s,'2030-03-01T09:00:00-05:00','2030-03-01T10:00:00-05:00')""",
                (self.slot, self.pilot))
            conn.execute("""insert into pickup_appointments (request_id,pilot_id,slot_id,leader_id)
                values (%s,%s,%s,%s)""",
                (self.request, self.pilot, self.slot, self.leader))

    def _items(self, weight="2.000"):
        return [{"material_id": str(self.material), "weight_kg": weight}]

    def _balance_and_sum(self, client):
        with self.psycopg.connect(self.url) as conn:
            return conn.execute("""select u.points_balance,
                coalesce(sum(pm.amount), 0) from users u
                left join point_movements pm on pm.client_id = u.id
                where u.id = %s group by u.id""", (client,)).fetchone()

    def test_migrations_clean_and_repeatable(self):
        from db.migrate import migrate
        self.assertEqual(self.applied, ["001_initial.sql", "002_api_integration.sql"])
        self.assertEqual(self.applied_again, [])
        self.assertEqual(migrate(self.url), [])
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute("select count(*) from users where id=%s",
                                          (self.client,)).fetchone()[0], 1)

    def test_api_migration_preserves_existing_pilot_data(self):
        from psycopg import sql
        from psycopg.conninfo import make_conninfo

        from db.migrate import MIGRATIONS, migrate

        base = os.environ["TEST_DATABASE_URL"]
        namespace = f"ec_upgrade_{uuid4().hex}"
        schema = sql.Identifier(namespace)
        with self.psycopg.connect(base, autocommit=True) as conn:
            conn.execute(sql.SQL("create schema {}").format(schema))
        self.addCleanup(self._drop_schema, base, schema)
        url = make_conninfo(base, options=f"-c search_path={namespace}")
        with tempfile.TemporaryDirectory() as temp:
            first = "001_initial.sql"
            (Path(temp) / first).write_bytes((MIGRATIONS / first).read_bytes())
            with patch("db.migrate.MIGRATIONS", Path(temp)):
                self.assertEqual(migrate(url), [first])

        demo = (MIGRATIONS.parent / "demo.sql").read_text()
        initial_demo = demo.split("-- Pilot catalog and a fictional shift")[0]
        with self.psycopg.connect(url, autocommit=True) as conn:
            conn.execute(initial_demo)
        self.assertEqual(migrate(url), ["002_api_integration.sql"])
        self.assertEqual(migrate(url), [])
        with self.psycopg.connect(url) as conn:
            row = conn.execute("""
                select p.status, n.message, s.starts_at is not null
                from pickup_requests p join pickup_notices n on n.request_id = p.id
                join pickup_appointments a on a.request_id = p.id
                join pickup_slots s on s.id = a.slot_id
            """).fetchone()
            self.assertEqual(row, ("programada", "Cita de prueba creada.", True))

    def _drop_schema(self, base, schema):
        from psycopg import sql

        with self.psycopg.connect(base, autocommit=True) as conn:
            conn.execute(sql.SQL("drop schema {} cascade").format(schema))

    def test_constraints_reject_duplicate_document_cross_pilot_and_bad_weight(self):
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            doc = conn.execute("select document_number from users where id=%s", (self.client,)).fetchone()[0]
            with self.assertRaises(self.psycopg.errors.UniqueViolation):
                conn.execute("""insert into users
                    (pilot_id,email,document_number,full_name,role,password_hash)
                    values (%s,%s,%s,'Duplicado','cliente','TEST_ONLY')""",
                    (self.pilot, f"{uuid4()}@example.invalid", doc))
            with self.assertRaises(self.psycopg.Error):
                conn.execute("update users set points_balance=1 where id=%s", (self.client,))
            with self.assertRaises(self.psycopg.errors.NotNullViolation):
                conn.execute("""insert into pickup_appointments
                    (request_id,pilot_id,slot_id,leader_id) values (%s,%s,null,%s)""",
                    (uuid4(), self.pilot, self.leader))
            other_pilot, other_slot = uuid4(), uuid4()
            conn.execute("insert into pilots(id,name,city) values (%s,%s,'Otra')",
                         (other_pilot, str(other_pilot)))
            conn.execute("""insert into pickup_slots(id,pilot_id,starts_at,ends_at)
                values (%s,%s,'2030-03-02T09:00:00Z','2030-03-02T10:00:00Z')""",
                (other_slot, other_pilot))
            second_request = uuid4()
            conn.execute("""insert into pickup_requests
                (id,client_id,pilot_id,address,status)
                values (%s,%s,%s,'Otra dirección ficticia','programada')""",
                (second_request, self.client, self.pilot))
            with self.assertRaises(self.psycopg.errors.ForeignKeyViolation):
                conn.execute("""insert into pickup_appointments
                    (request_id,pilot_id,slot_id,leader_id) values (%s,%s,%s,%s)""",
                    (second_request, self.pilot, other_slot, self.leader))
        from db.operations import close_pickup
        delivery_id, _ = close_pickup(self.url, self.request, self.leader, self.worker, self._items())
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            rule = conn.execute("select id from point_rules where material_id=%s", (self.material,)).fetchone()[0]
            other_material = uuid4()
            conn.execute("insert into materials(id,code,name) values (%s,%s,'Papel')",
                         (other_material, str(other_material)))
            conn.execute("""insert into point_rules(material_id,points_per_kg,valid_from)
                values (%s,10,'2020-01-01T00:00:00Z')""", (other_material,))
            other_rule = conn.execute("select id from point_rules where material_id=%s",
                                      (other_material,)).fetchone()[0]
            with self.assertRaises(self.psycopg.errors.CheckViolation):
                conn.execute("""insert into delivery_items
                    (delivery_id,material_id,rule_id,weight_kg,points_per_kg,awarded_points)
                    values (%s,%s,%s,-1,10,0)""", (delivery_id, other_material, other_rule))
            with self.assertRaises(self.psycopg.errors.ForeignKeyViolation):
                conn.execute("""insert into delivery_items
                    (delivery_id,material_id,rule_id,weight_kg,points_per_kg,awarded_points)
                    values (%s,%s,%s,1,10,10)""", (delivery_id, other_material, rule))

    def test_concurrent_close_creates_one_credit(self):
        from db.operations import close_pickup
        def close():
            return close_pickup(self.url, self.request, self.leader, self.worker, self._items())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: close(), range(2)))
        self.assertEqual(results[0], results[1])
        with self.psycopg.connect(self.url) as conn:
            count = conn.execute("select count(*) from point_movements where delivery_id=%s",
                                 (results[0][0],)).fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(self._balance_and_sum(self.client), (20, 20))

    def test_failed_close_rolls_back_everything(self):
        from db.operations import DomainError, close_pickup
        with self.assertRaises(DomainError):
            close_pickup(self.url, self.request, self.leader, self.worker,
                         [{"material_id": str(uuid4()), "weight_kg": "2.000"}])
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute("select count(*) from deliveries where request_id=%s",
                                          (self.request,)).fetchone()[0], 0)
            self.assertEqual(conn.execute("select status from pickup_requests where id=%s",
                                          (self.request,)).fetchone()[0], "programada")
        self.assertEqual(self._balance_and_sum(self.client), (0, 0))

    def test_direct_delivery_key_is_idempotent(self):
        from db.operations import record_direct_delivery
        key = "direct-" + str(self.client)
        first = record_direct_delivery(self.url, self.client, self.leader, self.worker,
                                       key, self._items())
        self.assertEqual(record_direct_delivery(self.url, self.client, self.leader,
                                                self.worker, key, self._items()), first)
        self.assertEqual(self._balance_and_sum(self.client), (20, 20))
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute("select count(*) from deliveries where external_key=%s",
                                          (key,)).fetchone()[0], 1)

    def test_concurrent_redemptions_respect_last_stock_and_balance(self):
        from db.operations import DomainError, confirm_redemption, close_pickup
        close_pickup(self.url, self.request, self.leader, self.worker, self._items("4.000"))
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute("update rewards set stock=1 where id=%s", (self.reward,))
        def redeem(code):
            try:
                return confirm_redemption(self.url, self.client, self.reward, code)
            except DomainError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(redeem, ["code-a-" + str(self.client), "code-b-" + str(self.client)]))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(self._balance_and_sum(self.client), (20, 20))
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute("select stock from rewards where id=%s",
                                          (self.reward,)).fetchone()[0], 0)

    def test_two_clients_compete_for_last_reward(self):
        from db.operations import DomainError, confirm_redemption, record_direct_delivery
        second_client = uuid4()
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute("""insert into users
                (id,pilot_id,email,document_number,full_name,role,password_hash)
                values (%s,%s,%s,%s,'Segundo cliente','cliente','TEST_ONLY')""",
                (second_client, self.pilot, f"{second_client}@example.invalid",
                 "2" + str(second_client.int)[:15]))
            conn.execute("update rewards set stock=1 where id=%s", (self.reward,))
        for client in (self.client, second_client):
            record_direct_delivery(self.url, client, self.leader, self.worker,
                                   "credit-" + str(client), self._items())
        def redeem(client):
            try:
                return confirm_redemption(self.url, client, self.reward, "code-" + str(client))
            except DomainError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(redeem, (self.client, second_client)))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(sum(self._balance_and_sum(c)[0] for c in (self.client, second_client)), 20)
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute("select stock from rewards where id=%s",
                                          (self.reward,)).fetchone()[0], 0)

    def test_same_balance_cannot_fund_two_redemptions(self):
        from db.operations import DomainError, close_pickup, confirm_redemption
        close_pickup(self.url, self.request, self.leader, self.worker, self._items())
        def redeem(code):
            try:
                return confirm_redemption(self.url, self.client, self.reward, code)
            except DomainError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(redeem, ["balance-a-" + str(self.client),
                                             "balance-b-" + str(self.client)]))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(self._balance_and_sum(self.client), (0, 0))
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute("select stock from rewards where id=%s",
                                          (self.reward,)).fetchone()[0], 1)

    def test_reused_code_and_debit_failure_do_not_consume_twice(self):
        from db.operations import confirm_redemption, close_pickup, record_direct_delivery
        close_pickup(self.url, self.request, self.leader, self.worker, self._items())
        code = "once-" + str(self.client)
        first = confirm_redemption(self.url, self.client, self.reward, code)
        self.assertEqual(confirm_redemption(self.url, self.client, self.reward, code), first)
        self.assertEqual(self._balance_and_sum(self.client), (0, 0))
        record_direct_delivery(self.url, self.client, self.leader, self.worker,
                               "extra-" + str(self.client), self._items())
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute("""create function reject_debit_for_test() returns trigger language plpgsql as $$
                begin if new.amount < 0 then raise exception 'injected debit failure'; end if;
                return new; end $$""")
            conn.execute("""create trigger reject_debit_for_test before insert on point_movements
                for each row execute function reject_debit_for_test()""")
        try:
            with self.assertRaises(self.psycopg.Error):
                confirm_redemption(self.url, self.client, self.reward, "fail-" + str(self.client))
            with self.psycopg.connect(self.url) as conn:
                self.assertEqual(conn.execute("select stock from rewards where id=%s",
                                              (self.reward,)).fetchone()[0], 1)
                self.assertEqual(conn.execute("select count(*) from redemptions where client_id=%s",
                                              (self.client,)).fetchone()[0], 1)
            self.assertEqual(self._balance_and_sum(self.client), (20, 20))
        finally:
            with self.psycopg.connect(self.url, autocommit=True) as conn:
                conn.execute("drop trigger reject_debit_for_test on point_movements")
                conn.execute("drop function reject_debit_for_test()")


if __name__ == "__main__":
    unittest.main()
