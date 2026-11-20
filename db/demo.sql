-- Fictional local data. Run only in a disposable development database after migration.
insert into pilots (id, name, city) values
    ('10000000-0000-4000-8000-000000000001', 'Piloto Barranquilla', 'Barranquilla');
insert into users (id, pilot_id, email, document_number, full_name, role, password_hash) values
    ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     'ana.demo@example.invalid', '100000001', 'Ana Demo', 'cliente', 'DEMO_NO_LOGIN'),
    ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001',
     'lider.demo@example.invalid', null, 'Líder Demo', 'lider', 'DEMO_NO_LOGIN');
insert into field_workers (id, pilot_id, full_name) values
    ('30000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     'Equipo Demo');
insert into materials (id, code, name) values
    ('40000000-0000-4000-8000-000000000001', 'PET', 'Plástico PET'),
    ('40000000-0000-4000-8000-000000000002', 'PAPEL', 'Papel');
insert into point_rules (material_id, points_per_kg, valid_from) values
    ('40000000-0000-4000-8000-000000000001', 10, '2020-01-01T00:00:00Z'),
    ('40000000-0000-4000-8000-000000000002', 5, '2020-01-01T00:00:00Z');
insert into rewards (id, pilot_id, code, name, points_cost, stock) values
    ('50000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     'DEMO-1', 'Premio ficticio', 20, 2);
insert into pickup_requests (id, client_id, pilot_id, address, status) values
    ('60000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001',
     '10000000-0000-4000-8000-000000000001', 'Calle ficticia 123', 'programada');
insert into pickup_slots (id, pilot_id, starts_at, ends_at) values
    ('70000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     '2030-03-01T09:00:00-05:00', '2030-03-01T10:00:00-05:00');
insert into pickup_appointments (request_id, pilot_id, slot_id, leader_id) values
    ('60000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     '70000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000002');
insert into content_entries (pilot_id, author_id, slug, title, body, status, published_at) values
    ('10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000002',
     'reciclaje-demo', 'Reciclaje de prueba', 'Contenido ficticio.', 'publicado', now());
insert into pickup_notices (request_id, pilot_id, author_id, message) values
    ('60000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     '20000000-0000-4000-8000-000000000002',
     'Cita de prueba creada.');
insert into request_audit (request_id, pilot_id, actor_id, from_status, to_status) values
    ('60000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
     '20000000-0000-4000-8000-000000000002',
     'recibida', 'programada');
