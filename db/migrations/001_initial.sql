-- EcoConecta: single ordered SQL migration stream. All timestamps are timestamptz.
create table pilots (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    city text not null,
    timezone text not null default 'America/Bogota',
    active boolean not null default true
);

create table users (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid references pilots(id),
    email text not null,
    document_number text,
    full_name text not null,
    role text not null check (role in ('cliente', 'lider', 'admin')),
    password_hash text not null,
    points_balance bigint not null default 0 check (points_balance >= 0),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    unique (id, pilot_id),
    check (role <> 'cliente' or (pilot_id is not null and document_number is not null)),
    check (document_number is null or document_number ~ '^[0-9]{5,20}$')
);
create unique index users_email_lower_uq on users (lower(email));
create unique index users_document_number_uq on users (document_number) where document_number is not null;
create index users_pilot_role_idx on users (pilot_id, role);

-- Field workers have no authentication credentials.
create table field_workers (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid not null references pilots(id),
    full_name text not null,
    active boolean not null default true,
    unique (id, pilot_id)
);
create index field_workers_pilot_idx on field_workers (pilot_id);

create table content_entries (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid references pilots(id),
    author_id uuid not null references users(id),
    slug text not null unique,
    title text not null,
    body text not null,
    status text not null check (status in ('borrador', 'publicado', 'archivado')),
    published_at timestamptz,
    created_at timestamptz not null default now(),
    check ((status = 'publicado') = (published_at is not null)),
    foreign key (author_id, pilot_id) references users(id, pilot_id)
);
create index content_entries_pilot_status_idx on content_entries (pilot_id, status, published_at desc);
create index content_entries_author_idx on content_entries (author_id);

create table pickup_requests (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null,
    pilot_id uuid not null,
    address text not null,
    notes text,
    status text not null default 'recibida'
        check (status in ('recibida', 'programada', 'recolectada', 'cancelada', 'revision')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (client_id, pilot_id) references users(id, pilot_id),
    unique (id, client_id, pilot_id),
    unique (id, pilot_id)
);
create index pickup_requests_client_idx on pickup_requests (client_id, created_at desc);
create index pickup_requests_pilot_status_idx on pickup_requests (pilot_id, status, created_at);

create table pickup_notices (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null,
    pilot_id uuid not null,
    author_id uuid not null,
    message text not null,
    created_at timestamptz not null default now(),
    foreign key (request_id, pilot_id) references pickup_requests(id, pilot_id),
    foreign key (author_id, pilot_id) references users(id, pilot_id)
);
create index pickup_notices_request_idx on pickup_notices (request_id, created_at);
create index pickup_notices_author_idx on pickup_notices (author_id);

create table pickup_slots (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid not null references pilots(id),
    starts_at timestamptz not null,
    ends_at timestamptz not null,
    active boolean not null default true,
    check (ends_at > starts_at),
    unique (id, pilot_id),
    unique (pilot_id, starts_at)
);
create index pickup_slots_available_idx on pickup_slots (pilot_id, starts_at) where active;

-- A row is always a complete appointment; one request and one slot per appointment.
create table pickup_appointments (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null unique,
    pilot_id uuid not null,
    slot_id uuid not null unique,
    leader_id uuid not null,
    created_at timestamptz not null default now(),
    foreign key (request_id, pilot_id) references pickup_requests(id, pilot_id),
    foreign key (slot_id, pilot_id) references pickup_slots(id, pilot_id),
    foreign key (leader_id, pilot_id) references users(id, pilot_id)
);
create index pickup_appointments_pilot_idx on pickup_appointments (pilot_id);
create index pickup_appointments_leader_idx on pickup_appointments (leader_id);

create table request_audit (
    id bigint generated always as identity primary key,
    request_id uuid not null,
    pilot_id uuid not null,
    actor_id uuid not null,
    from_status text,
    to_status text not null,
    detail jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (request_id, pilot_id) references pickup_requests(id, pilot_id),
    foreign key (actor_id, pilot_id) references users(id, pilot_id)
);
create index request_audit_request_idx on request_audit (request_id, created_at);
create index request_audit_actor_idx on request_audit (actor_id);

create table materials (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    active boolean not null default true
);

create table point_rules (
    id uuid primary key default gen_random_uuid(),
    material_id uuid not null references materials(id),
    points_per_kg numeric(12,3) not null check (points_per_kg >= 0),
    valid_from timestamptz not null,
    valid_until timestamptz,
    unique (id, material_id),
    check (valid_until is null or valid_until > valid_from)
);
create index point_rules_lookup_idx on point_rules (material_id, valid_from desc);

create table deliveries (
    id uuid primary key default gen_random_uuid(),
    kind text not null check (kind in ('pickup', 'direct')),
    request_id uuid unique,
    client_id uuid not null,
    pilot_id uuid not null,
    field_worker_id uuid not null,
    closed_by_id uuid not null,
    external_key text unique,
    closed_at timestamptz not null default now(),
    foreign key (client_id, pilot_id) references users(id, pilot_id),
    foreign key (field_worker_id, pilot_id) references field_workers(id, pilot_id),
    foreign key (closed_by_id, pilot_id) references users(id, pilot_id),
    foreign key (request_id, client_id, pilot_id)
        references pickup_requests(id, client_id, pilot_id),
    unique (id, client_id),
    check ((kind = 'pickup' and request_id is not null and external_key is null)
        or (kind = 'direct' and request_id is null and external_key is not null))
);
create index deliveries_client_idx on deliveries (client_id, closed_at desc);
create index deliveries_pilot_idx on deliveries (pilot_id, closed_at desc);
create index deliveries_field_worker_idx on deliveries (field_worker_id);
create index deliveries_closed_by_idx on deliveries (closed_by_id);

-- One line per material; a close may contain any number of different materials.
create table delivery_items (
    delivery_id uuid not null references deliveries(id),
    material_id uuid not null references materials(id),
    rule_id uuid not null,
    weight_kg numeric(12,3) not null check (weight_kg > 0 and weight_kg <= 10000),
    points_per_kg numeric(12,3) not null check (points_per_kg >= 0),
    awarded_points bigint not null check (awarded_points >= 0),
    primary key (delivery_id, material_id),
    foreign key (rule_id, material_id) references point_rules(id, material_id)
);
create index delivery_items_material_idx on delivery_items (material_id);
create index delivery_items_rule_idx on delivery_items (rule_id);

create table rewards (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid not null references pilots(id),
    code text not null,
    name text not null,
    points_cost bigint not null check (points_cost > 0),
    stock integer not null check (stock >= 0),
    active boolean not null default true,
    unique (pilot_id, code),
    unique (id, pilot_id)
);
create index rewards_pilot_active_idx on rewards (pilot_id, active);

create table redemptions (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null,
    pilot_id uuid not null,
    reward_id uuid not null,
    code text not null unique,
    points_cost bigint not null check (points_cost > 0),
    status text not null default 'confirmado' check (status in ('confirmado')),
    confirmed_at timestamptz not null default now(),
    foreign key (client_id, pilot_id) references users(id, pilot_id),
    foreign key (reward_id, pilot_id) references rewards(id, pilot_id),
    unique (id, client_id)
);
create index redemptions_client_idx on redemptions (client_id, confirmed_at desc);
create index redemptions_reward_idx on redemptions (reward_id);

create function consume_reward_stock() returns trigger language plpgsql as $$
begin
    update rewards set stock = stock - 1
    where id = new.reward_id and stock > 0 and active
      and points_cost = new.points_cost;
    if not found then
        raise exception 'reward unavailable or price changed' using errcode = 'P0001';
    end if;
    return new;
end $$;
create trigger redemption_insert after insert on redemptions
    for each row execute function consume_reward_stock();

create table point_movements (
    id bigint generated always as identity primary key,
    client_id uuid not null references users(id),
    delivery_id uuid unique,
    redemption_id uuid unique,
    amount bigint not null check (amount <> 0),
    created_at timestamptz not null default now(),
    foreign key (delivery_id, client_id) references deliveries(id, client_id),
    foreign key (redemption_id, client_id) references redemptions(id, client_id),
    check ((delivery_id is not null and redemption_id is null and amount > 0)
        or (delivery_id is null and redemption_id is not null and amount < 0))
);
create index point_movements_client_idx on point_movements (client_id, id);

-- The ledger is the sole writer of the cached balance. A failed debit aborts the transaction.
create function guard_user_balance() returns trigger language plpgsql as $$
begin
    if tg_op = 'INSERT' then
        if new.points_balance <> 0 then
            raise exception 'initial balance must be zero' using errcode = 'P0001';
        end if;
    elsif new.points_balance is distinct from old.points_balance
          and pg_trigger_depth() < 2 then
        raise exception 'balance can only change through point movements' using errcode = 'P0001';
    end if;
    return new;
end $$;
create trigger users_balance_guard before insert or update on users
    for each row execute function guard_user_balance();

create function apply_point_movement() returns trigger language plpgsql as $$
declare expected_amount bigint;
begin
    if new.delivery_id is not null then
        select coalesce(sum(awarded_points), 0) into expected_amount
        from delivery_items where delivery_id = new.delivery_id;
    else
        select -points_cost into expected_amount
        from redemptions where id = new.redemption_id;
    end if;
    if new.amount is distinct from expected_amount then
        raise exception 'movement amount differs from source' using errcode = 'P0001';
    end if;
    update users set points_balance = points_balance + new.amount
    where id = new.client_id and role = 'cliente'
      and points_balance + new.amount >= 0;
    if not found then
        raise exception 'insufficient points or invalid client' using errcode = 'P0001';
    end if;
    return new;
end $$;
create trigger point_movement_insert after insert on point_movements
    for each row execute function apply_point_movement();

create function reject_point_movement_change() returns trigger language plpgsql as $$
begin
    raise exception 'point movements are immutable' using errcode = 'P0001';
end $$;
create trigger point_movement_immutable before update or delete on point_movements
    for each row execute function reject_point_movement_change();
