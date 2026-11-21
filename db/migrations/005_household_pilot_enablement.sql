-- RN-08: la participación en el piloto se configura por cuenta, también para hogares.
-- Los hogares registrados antes de esta migración ya podían solicitar recolecciones;
-- se conservan habilitados. Los hogares nuevos quedan pendientes hasta que
-- administración los habilite (users.pilot_enabled conserva su default false).
update users set pilot_enabled = true
where role = 'cliente' and kind = 'household' and not pilot_enabled;
