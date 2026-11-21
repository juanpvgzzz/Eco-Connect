-- Reglas de puntos configurables por administración. Los valores son
-- provisionales hasta su validación por la Fundación Santo Domingo: los
-- documentos de FSD no definen equivalencias oficiales.
alter table point_rules
    add column provisional boolean not null default true,
    add column note text,
    add column created_by uuid references users(id),
    add column created_at timestamptz not null default now();
