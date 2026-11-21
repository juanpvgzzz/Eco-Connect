import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Inbox, Recycle, Sprout, UserRound } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { useMediaQuery } from "../../hooks/useMediaQuery.js";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { bogotaDayKey, formatDateTime, formatTime } from "../../utils/dateTime.js";
import { addDays, bogotaHour, dayName, dayShort, mondayOf, rangeLabel, todayKey, weekDays } from "./week.js";

const FLOW = { huerta: { label: "Orgánico", icon: Sprout, tone: "organic" }, reciclaje: { label: "Reciclable", icon: Recycle, tone: "recycle" } };
const shortId = (id) => `#${String(id).slice(0, 8)}`;
const material = (r) => r.solicitud?.material || r.material || r.entrega?.material || "Recogida";

// Calendario de recolecciones (tipo horario escolar). Solo muestra recogidas
// con programación confirmada (fecha, hora y responsable) del rango visible,
// consultadas a FastAPI por semana. Las pendientes van en una sección aparte.
// `flows`: colectivos que puede elegir administración; la coordinadora no elige.
export function WeekCalendar({ token, onOpen, flows }) {
  const [monday, setMonday] = useState(() => mondayOf(todayKey()));
  const [flow, setFlow] = useState("");
  const [week, setWeek] = useState(null);
  const [error, setError] = useState("");
  const wide = useMediaQuery("(min-width: 1024px)");
  const today = todayKey();

  const load = useCallback(() => {
    setWeek(null);
    setError("");
    const params = new URLSearchParams({ desde: monday, ...(flow ? { flujo: flow } : {}) });
    request(`/recolecciones/calendario?${params}`, { token })
      .then(setWeek)
      .catch((e) => setError(friendlyError(e)));
  }, [monday, flow, token]);
  useEffect(load, [load]);

  const days = weekDays(monday);
  const byDay = useMemo(() => {
    const map = Object.fromEntries(days.map((d) => [d, []]));
    for (const r of week?.programadas || []) map[bogotaDayKey(r.cita)]?.push(r);
    return map;
  }, [week, monday]); // eslint-disable-line react-hooks/exhaustive-deps
  const hours = useMemo(() => {
    const used = (week?.programadas || []).map((r) => bogotaHour(r.cita));
    const from = Math.min(7, ...used);
    const to = Math.max(17, ...used);
    return Array.from({ length: to - from + 1 }, (_, i) => from + i);
  }, [week]);

  const card = (r) => {
    const f = FLOW[r.flujo] || FLOW.huerta;
    const Icon = f.icon;
    return (
      <button key={r.id} type="button" className="cal-card" data-tone={f.tone} onClick={() => onOpen(r)}
        aria-label={`${formatTime(r.cita)}, ${f.label}, ${material(r)}, solicitud ${shortId(r.id)}. Abrir detalle`}>
        <span className="cal-card-time data">{formatTime(r.cita)}</span>
        <span className="cal-card-type"><Icon size={16} /> {f.label}</span>
        <span className="cal-card-material">{material(r)}</span>
        <CollectionStatus value={r.estado} />
        {r.nombre_responsable && <span className="cal-card-who"><UserRound size={16} /> {r.nombre_responsable}</span>}
        <span className="cal-card-id data">{shortId(r.id)}</span>
      </button>
    );
  };

  return (
    <section className="calendar-ops" aria-labelledby="cal-title">
      <div className="cal-head">
        <div>
          <h2 id="cal-title">Calendario de recolecciones</h2>
          <p className="cal-range" aria-live="polite">{rangeLabel(monday)}</p>
        </div>
        <div className="cal-controls">
          <Button variant="secondary" size="lg" icon={ChevronLeft} onClick={() => setMonday(addDays(monday, -7))}>Semana anterior</Button>
          <Button variant="secondary" size="lg" disabled={monday === mondayOf(today)} onClick={() => setMonday(mondayOf(today))}>Esta semana</Button>
          <Button variant="secondary" size="lg" iconEnd={ChevronRight} onClick={() => setMonday(addDays(monday, 7))}>Semana siguiente</Button>
        </div>
      </div>
      {flows && (
        <div className="cal-filter" role="group" aria-label="Colectivo">
          {[["", "Ambos colectivos"], ...flows.map((f) => [f, f === "huerta" ? "Huerteros (orgánicos)" : "Recicladores (reciclables)"])].map(([value, text]) => (
            <Button key={value || "todos"} size="lg" variant={flow === value ? "primary" : "secondary"} aria-pressed={flow === value} onClick={() => setFlow(value)}>{text}</Button>
          ))}
        </div>
      )}
      {error && <Alert tone="error" title="No se pudo cargar el calendario">{error} <Button variant="ghost" onClick={load}>Reintentar</Button></Alert>}
      {!week && !error && <Loading>Cargando la semana…</Loading>}

      {week && (
        <>
          {!week.programadas.length && (
            <EmptyState icon={CalendarDays} title="No hay recogidas programadas esta semana">
              Las recogidas aparecen aquí cuando tienen fecha, hora y responsable confirmados.
            </EmptyState>
          )}
          {week.programadas.length > 0 && wide && (
            <div className="cal-grid-wrap" role="region" aria-label="Horario semanal" tabIndex={0}>
              <table className="cal-grid">
                <caption className="visually-hidden">Recogidas programadas por día y hora, {rangeLabel(monday)}</caption>
                <thead>
                  <tr>
                    <th scope="col" className="cal-hour-head">Hora</th>
                    {days.map((d) => (
                      <th scope="col" key={d} data-today={d === today || undefined}>
                        <span className="cal-day-name">{dayName(d)}</span>
                        <span className="cal-day-date">{dayShort(d)}{d === today ? " · Hoy" : ""}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {hours.map((h) => (
                    <tr key={h}>
                      <th scope="row" className="cal-hour">{formatTime(`${monday}T${String(h).padStart(2, "0")}:00`)}</th>
                      {days.map((d) => (
                        <td key={d} data-today={d === today || undefined}>
                          {byDay[d].filter((r) => bogotaHour(r.cita) === h).map(card)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {week.programadas.length > 0 && !wide && (
            <ol className="cal-agenda">
              {days.filter((d) => byDay[d].length).map((d) => (
                <li key={d} className="cal-agenda-day" data-today={d === today || undefined}>
                  <h3>{dayName(d)} {dayShort(d)}{d === today ? " · Hoy" : ""}</h3>
                  <div className="cal-agenda-items">{byDay[d].map(card)}</div>
                </li>
              ))}
            </ol>
          )}

          <section className="cal-pending" aria-labelledby="cal-pending-title">
            <h3 id="cal-pending-title"><Inbox size={22} /> Pendientes de programar ({week.pendientes.length})</h3>
            <p className="muted">Aún no tienen fecha, hora y responsable confirmados, por eso no aparecen en el calendario.</p>
            {week.pendientes.length ? (
              <ul className="cal-pending-list">
                {week.pendientes.map((r) => (
                  <li key={r.id}>
                    <button type="button" className="cal-pending-item" onClick={() => onOpen(r)}>
                      <span className="cal-card-type">{(FLOW[r.flujo] || FLOW.huerta).label}</span>
                      <span className="cal-card-material">{material(r)}</span>
                      <CollectionStatus value={r.estado} />
                      <span className="muted">Solicitada: {formatDateTime(r.creada)}</span>
                      <span className="cal-card-id data">{shortId(r.id)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <p>No hay solicitudes pendientes.</p>}
          </section>
        </>
      )}
    </section>
  );
}
