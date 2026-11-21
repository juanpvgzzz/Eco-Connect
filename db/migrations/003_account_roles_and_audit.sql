-- Enable authenticated field workers and keep an auditable record of role changes.
alter table users drop constraint users_role_check;
alter table users add constraint users_role_check
    check (role in ('cliente', 'lider', 'admin', 'recolector'));

alter table field_workers
    add column account_id uuid,
    add column collective_id uuid,
    add foreign key (account_id, pilot_id) references users(id, pilot_id),
    add foreign key (collective_id, pilot_id) references collectives(id, pilot_id);
create unique index field_workers_account_uq on field_workers (account_id)
    where account_id is not null;

create table account_authorization_audit (
    id bigint generated always as identity primary key,
    pilot_id uuid not null references pilots(id),
    actor_id uuid references users(id),
    target_id uuid not null references users(id),
    action text not null,
    previous_role text,
    new_role text not null,
    previous_collective_id uuid,
    new_collective_id uuid,
    created_at timestamptz not null default now(),
    foreign key (previous_collective_id, pilot_id) references collectives(id, pilot_id),
    foreign key (new_collective_id, pilot_id) references collectives(id, pilot_id)
);
create index account_authorization_audit_pilot_date_idx
    on account_authorization_audit (pilot_id, created_at desc);
