import { CalendarDays, ChevronRight, Clock3 } from "../../components/icons.jsx";
import { BOGOTA_ZONE, formatDateTime, formatTime, timestampMillis } from "../../utils/dateTime.js";

const badgeDate = new Intl.DateTimeFormat("es-CO", { timeZone: BOGOTA_ZONE, day: "numeric", month: "short" });

// Próxima recogida confirmada (GET /community/appointments). Solo muestra
// fecha y hora si el colectivo la programó; nunca deduce «mañana» ni horarios.
export function NextPickup({ appointments, pending, onDetails }) {
  const now = Date.now();
  const next = appointments
    .filter((a) => timestampMillis(a.scheduled_at) >= now)
    .sort((a, b) => timestampMillis(a.scheduled_at) - timestampMillis(b.scheduled_at))[0];
  const date = next && Object.fromEntries(badgeDate.formatToParts(timestampMillis(next.scheduled_at)).map(({ type, value }) => [type, value]));
  return (
    <section className="next-pickup" aria-labelledby="next-pickup-title" data-pickup={next ? "scheduled" : pending > 0 ? "pending" : "empty"}>
      {date ? (
        <span className="next-pickup-date" aria-hidden="true"><strong>{date.day}</strong><span>{date.month}</span></span>
      ) : (
        <span className="next-pickup-icon" aria-hidden="true">{pending > 0 ? <Clock3 size={23} /> : <CalendarDays size={23} />}</span>
      )}
      <div className="next-pickup-content">
        <h2 id="next-pickup-title">Próxima recogida</h2>
        {next ? (
          <div className="next-pickup-details">
            <time dateTime={next.scheduled_at}>
              <span className="visually-hidden">{formatDateTime(next.scheduled_at)}</span>
              <span aria-hidden="true">{formatTime(next.scheduled_at)}</span>
            </time>
            {next.responsible_name && <p>Responsable: {next.responsible_name}</p>}
          </div>
        ) : (
          <>
            <p>{pending > 0
              ? `${pending === 1 ? "Tienes 1 solicitud" : `Tienes ${pending} solicitudes`} esperando confirmación.`
              : "Todavía no tienes recogidas programadas."}</p>
            {pending > 0 && <span className="next-pickup-pending"><Clock3 size={14} /> Esperando confirmación</span>}
          </>
        )}
        {onDetails && <button type="button" className="home-text-action" onClick={onDetails}>Ver detalle <ChevronRight size={16} /></button>}
      </div>
    </section>
  );
}
