import { useMemo, useState } from "react";
import { ArrowLeft, CalendarDays, ChevronLeft, ChevronRight, UserRound } from "../../components/icons.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { flowName, flowOf } from "../../utils/format.js";
import { bogotaDayKey, formatDateTime, formatFullDate, formatMonth, timestampMillis } from "../../utils/dateTime.js";

const WEEK = [["L", "Lunes"], ["M", "Martes"], ["X", "Miércoles"], ["J", "Jueves"], ["V", "Viernes"], ["S", "Sábado"], ["D", "Domingo"]];
const pad = (n) => String(n).padStart(2, "0");

// Mis recogidas programadas: calendario mensual construido solo con las citas
// confirmadas que devuelve GET /community/appointments, y la lista debajo.
export function CalendarView({ appointments, rows, onBack }) {
  const byDay = useMemo(() => {
    const map = {};
    for (const a of appointments) {
      if (Number.isFinite(timestampMillis(a.scheduled_at))) (map[bogotaDayKey(a.scheduled_at)] ||= []).push(a);
    }
    return map;
  }, [appointments]);
  const now = Date.now();
  const upcoming = appointments
    .filter((a) => timestampMillis(a.scheduled_at) >= now)
    .sort((a, b) => timestampMillis(a.scheduled_at) - timestampMillis(b.scheduled_at));
  const today = bogotaDayKey(now);
  const start = (bogotaDayKey(upcoming[0]?.scheduled_at) || today).split("-").map(Number);
  const [month, setMonth] = useState({ y: start[0], m: start[1] - 1 });

  const first = (new Date(Date.UTC(month.y, month.m, 1)).getUTCDay() + 6) % 7; // lunes = 0
  const days = new Date(Date.UTC(month.y, month.m + 1, 0)).getUTCDate();
  const cells = [...Array(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  const move = (delta) => setMonth(({ y, m }) => ({ y: m + delta < 0 ? y - 1 : m + delta > 11 ? y + 1 : y, m: (m + delta + 12) % 12 }));
  const title = formatMonth(`${month.y}-${pad(month.m + 1)}-01`);

  return (
    <section className="subview enter" aria-labelledby="calendar-title">
      <div className="view-head">
        <h1 id="calendar-title">Mis recogidas programadas</h1>
        <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Inicio</Button>
      </div>
      <div className="calendar card">
        <div className="calendar-head">
          <button type="button" className="calendar-nav" onClick={() => move(-1)} aria-label="Mes anterior"><ChevronLeft size={22} /></button>
          <h2 className="calendar-title" aria-live="polite">{title.charAt(0).toUpperCase() + title.slice(1)}</h2>
          <button type="button" className="calendar-nav" onClick={() => move(1)} aria-label="Mes siguiente"><ChevronRight size={22} /></button>
        </div>
        <table className="calendar-grid">
          <thead>
            <tr>{WEEK.map(([s, l]) => <th key={l} scope="col"><abbr title={l}>{s}</abbr></th>)}</tr>
          </thead>
          <tbody>
            {Array.from({ length: Math.ceil(cells.length / 7) }, (_, w) => (
              <tr key={w}>
                {cells.slice(w * 7, w * 7 + 7).concat(Array(7).fill(null)).slice(0, 7).map((d, i) => {
                  if (!d) return <td key={i} />;
                  const key = `${month.y}-${pad(month.m + 1)}-${pad(d)}`;
                  const count = byDay[key]?.length || 0;
                  return (
                    <td key={i}>
                      <span className="calendar-day" data-today={key === today || undefined} data-has={count > 0 || undefined}>
                        <time dateTime={key} aria-label={formatFullDate(key)}>{d}</time>
                        {count > 0 && <span className="calendar-dot" aria-hidden="true" />}
                        {count > 0 && <span className="visually-hidden">, {count} recogida{count > 1 ? "s" : ""} programada{count > 1 ? "s" : ""}</span>}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="calendar-legend"><span className="calendar-dot" aria-hidden="true" /> Día con recogida confirmada</p>
      </div>

      <h2 className="home-section-title">Próximas recogidas</h2>
      {upcoming.length ? (
        <ul className="appointment-list">
          {upcoming.map((a) => {
            const row = rows.find((r) => r.id === a.collection_id);
            const flow = flowOf(row?.flow);
            return (
              <li key={a.collection_id} className="appointment">
                <span className="appointment-date"><CalendarDays size={22} /></span>
                <div className="grid gap-1">
                  <p className="appointment-when"><time dateTime={a.scheduled_at}>{formatDateTime(a.scheduled_at)}</time></p>
                  <p>{[flow && flowName[flow], row?.material || row?.description].filter(Boolean).join(" · ")}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <CollectionStatus value={a.status} />
                    <span className="muted appointment-who"><UserRound size={16} /> {a.responsible_name}</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState icon={CalendarDays} title="Sin recogidas programadas">
          Cuando el colectivo confirme día, hora y responsable, aparecerá aquí.
        </EmptyState>
      )}
    </section>
  );
}
