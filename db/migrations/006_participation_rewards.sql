-- Proposed participation milestones, subject to Fundación Santo Domingo approval.
create table participation_milestones (
    pickups integer primary key check (pickups > 0),
    title text not null
);

insert into participation_milestones (pickups, title) values
    (1, 'Mi primera recogida'), (3, 'Vecino comprometido'),
    (5, 'Guardián verde'), (10, 'Héroe ambiental'), (20, 'Embajador EcoConecta');

-- The immutable ledger has at most one credit per delivery. A pickup has one
-- delivery per request. Direct deliveries keep their points without counting here.
create view confirmed_pickup_credits as
select m.id as movement_id, m.client_id, d.pilot_id, m.created_at
from point_movements m join deliveries d on d.id = m.delivery_id
where d.kind = 'pickup';

create table participation_recognitions (
    client_id uuid not null,
    pilot_id uuid not null,
    pickups integer not null references participation_milestones(pickups),
    unlocked_at timestamptz not null,
    foreign key (client_id, pilot_id) references users(id, pilot_id),
    primary key (client_id, pickups)
);

create function recognize_pickup_participation() returns trigger language plpgsql as $$
begin
    -- point_movement_insert runs first and holds the user's balance row lock.
    -- Concurrent credits for this user therefore advance milestones in order.
    insert into participation_recognitions (client_id, pilot_id, pickups, unlocked_at)
    select new.client_id, d.pilot_id, p.pickups, clock_timestamp()
    from deliveries d
    join participation_milestones p on p.pickups <= (
        select count(*) from confirmed_pickup_credits c where c.client_id = new.client_id
    )
    where d.id = new.delivery_id and d.kind = 'pickup'
    on conflict (client_id, pickups) do nothing;
    return new;
end $$;

create trigger point_movement_recognize_pickup after insert on point_movements
    for each row when (new.delivery_id is not null)
    execute function recognize_pickup_participation();

insert into participation_recognitions (client_id, pilot_id, pickups, unlocked_at)
select c.client_id, c.pilot_id, p.pickups, c.created_at
from (
    select *, row_number() over (partition by client_id order by movement_id) as pickups
    from confirmed_pickup_credits
) c join participation_milestones p on p.pickups = c.pickups
on conflict (client_id, pickups) do nothing;

-- Existing catalog entries require explicit validation before they can be offered.
alter table rewards
    add column validated_at timestamptz,
    add column validated_by uuid,
    add foreign key (validated_by, pilot_id) references users(id, pilot_id),
    add check ((validated_at is null) = (validated_by is null));

alter table redemption_codes add column reward_validated_at timestamptz;
create index redemption_codes_client_reward_idx
    on redemption_codes (client_id, reward_id, expires_at desc);

create or replace function consume_reward_stock() returns trigger language plpgsql as $$
begin
    update rewards set stock = stock - 1
    where id = new.reward_id and stock > 0 and active
        and validated_at is not null and points_cost = new.points_cost;
    if not found then
        raise exception 'reward unavailable or price changed' using errcode = 'P0001';
    end if;
    return new;
end $$;
