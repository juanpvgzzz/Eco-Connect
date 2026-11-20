-- Extend the shared tables for the API without changing the initial migration.
create table collectives (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid not null references pilots(id),
    flow text not null check (flow in ('huerta', 'reciclaje')),
    unique (id, pilot_id),
    unique (pilot_id, flow)
);

alter table users drop constraint users_document_number_check;
alter table users add check (document_number is null or document_number ~ '^[0-9]{1,20}$');
alter table users
    add column address text not null default '',
    add column phone text not null default '',
    add column kind text not null default 'household' check (kind in ('household', 'business')),
    add column pilot_enabled boolean not null default false,
    add column collective_id uuid,
    add foreign key (collective_id, pilot_id) references collectives(id, pilot_id);

create table account_sessions (
    token_digest text primary key,
    account_id uuid not null references users(id),
    created_at timestamptz not null,
    expires_at timestamptz not null,
    revoked_at timestamptz,
    check (expires_at > created_at)
);

create table account_login_attempts (
    attempt_key text primary key,
    failures integer not null,
    window_expires_at timestamptz not null,
    locked_until timestamptz
);
create index account_login_attempts_expiry_idx on account_login_attempts
    ((greatest(window_expires_at, locked_until)));

alter table content_entries
    add column category text not null default 'materials'
        check (category in ('materials', 'separation', 'garden', 'routes', 'schedules')),
    add column updated_at timestamptz;
update content_entries set updated_at = coalesce(published_at, created_at);
alter table content_entries alter column updated_at set not null;
alter table content_entries alter column updated_at set default now();

alter table pickup_requests
    add column flow text check (flow in ('huerta', 'reciclaje')),
    add column idempotency_key text,
    add column form jsonb,
    add unique (client_id, idempotency_key);
create index pickup_requests_flow_inbox_idx on pickup_requests (pilot_id, flow, status, created_at);

alter table pickup_slots drop constraint pickup_slots_pilot_id_starts_at_key;
alter table pickup_slots
    add column collective_id uuid,
    add foreign key (collective_id, pilot_id) references collectives(id, pilot_id),
    add unique nulls not distinct (pilot_id, collective_id, starts_at);

alter table pickup_appointments
    add column worker_id uuid,
    add foreign key (worker_id, pilot_id) references field_workers(id, pilot_id);

create table collection_shifts (
    id uuid primary key default gen_random_uuid(),
    collective_id uuid not null,
    pilot_id uuid not null,
    worker_id uuid not null,
    starts_at timestamptz not null,
    ends_at timestamptz not null,
    check (ends_at > starts_at),
    foreign key (collective_id, pilot_id) references collectives(id, pilot_id),
    foreign key (worker_id, pilot_id) references field_workers(id, pilot_id),
    unique (collective_id, starts_at)
);

alter table deliveries
    add column flow text check (flow in ('huerta', 'reciclaje')),
    add column api_result jsonb,
    add column api_key text;
create unique index deliveries_owner_api_key_uq on deliveries (closed_by_id, api_key)
    where api_key is not null;

-- Each event is an immutable snapshot used by the audit and notification views.
create table collection_events (
    id uuid primary key default gen_random_uuid(),
    pilot_id uuid not null references pilots(id),
    request_id uuid,
    delivery_id uuid,
    client_id uuid not null,
    flow text not null check (flow in ('huerta', 'reciclaje')),
    author_id uuid not null,
    kind text not null,
    snapshot jsonb not null,
    reason text,
    created_at timestamptz not null default now(),
    check ((request_id is null) <> (delivery_id is null)),
    foreign key (request_id, client_id, pilot_id)
        references pickup_requests(id, client_id, pilot_id),
    foreign key (delivery_id, client_id) references deliveries(id, client_id),
    foreign key (client_id, pilot_id) references users(id, pilot_id),
    foreign key (author_id, pilot_id) references users(id, pilot_id)
);
create index collection_events_request_idx on collection_events (request_id, created_at);
create index collection_events_delivery_idx on collection_events (delivery_id, created_at);
create index collection_events_client_idx on collection_events (client_id, created_at);
create index collection_events_flow_idx on collection_events (pilot_id, flow, created_at);

alter table rewards add column description text not null default '';
create table reward_stock_audit (
    id bigint generated always as identity primary key,
    reward_id uuid not null,
    pilot_id uuid not null,
    author_id uuid not null,
    quantity integer not null check (quantity >= 0),
    created_at timestamptz not null default now(),
    foreign key (reward_id, pilot_id) references rewards(id, pilot_id),
    foreign key (author_id, pilot_id) references users(id, pilot_id)
);

create table redemption_codes (
    code text primary key,
    client_id uuid not null,
    pilot_id uuid not null,
    reward_id uuid not null,
    expires_at timestamptz not null,
    foreign key (client_id, pilot_id) references users(id, pilot_id),
    foreign key (reward_id, pilot_id) references rewards(id, pilot_id)
);

alter table redemptions
    add column confirmed_by uuid,
    add foreign key (confirmed_by, pilot_id) references users(id, pilot_id);
