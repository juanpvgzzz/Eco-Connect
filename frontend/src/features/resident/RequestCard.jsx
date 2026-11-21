import { useId, useState } from "react";
import { CalendarClock, CalendarDays, ChevronDown, CircleCheck, Inbox, Recycle, Search, Sprout, X } from "../../components/icons.jsx";
import { RequestTimeline } from "./RequestTimeline.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { flowName, flowOf, formatAvailability, formatDay, formatWhen, nameOf, stageOf } from "../../utils/format.js";

const FLOW_ICON = { organic: Sprout, recyclable: Recycle };
const RECENT_STATUS = { pending: Inbox, review: Search, assigned: AssignedIcon, scheduled: CalendarClock, done: CircleCheck, cancelled: X };
const RECENT_STAGES = { assigned: "assigned", asignada: "assigned", completed: "done", completada: "done" };

function AssignedIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <circle cx="9" cy="8" r="4" /><path d="M2 20a7 7 0 0 1 10-6m3 2 2.5 2.5L22 14" />
    </svg>
  );
}

function RecentStatus({ value }) {
  const stage = RECENT_STAGES[value] || stageOf[value];
  const tone = Object.hasOwn(RECENT_STATUS, stage) ? stage : "unknown";
  const Icon = RECENT_STATUS[tone] || Inbox;
  const label = Object.hasOwn(nameOf, value) ? nameOf[value] : tone === "assigned" ? "Asignada" : value;
  return <span className="home-request-status" data-tone={tone}><Icon size={14} aria-hidden="true" />{label}</span>;
}

// Resumen de una solicitud: tipo, material real, estado y fecha. La dirección,
// la disponibilidad y las observaciones van en el detalle desplegable.
export function RequestCard({ row, appointment, fresh, token, showVisitInSummary = true, recent = false }) {
  const [open, setOpen] = useState(false);
  const detailId = useId();
  const flow = flowOf(row.flow);
  const FlowIcon = FLOW_ICON[flow];
  const material = row.material || row.description;
  const date = formatDay(row.created_at);
  const visit = formatWhen(appointment?.scheduled_at);
  const availability = formatAvailability(row.availability);
  return (
    <article className="request-card" data-recent={recent || undefined} data-new={fresh || undefined} data-flow={flow || undefined} aria-label={`Solicitud: ${material}`}>
      <span className="request-flow" aria-hidden="true">{FlowIcon && <FlowIcon size={22} />}</span>
      <div className="request-body">
        {recent ? (
          <div className="home-request-summary">
            <div className="home-request-info">
              {flow && <p className="request-type">{flowName[flow]}</p>}
              <h3 className="request-title">{material}</h3>
              <p className="home-request-meta">
                <span title={row.id}>#{row.id.slice(0, 8)}</span>
                {date && <time dateTime={row.created_at}>{date}</time>}
              </p>
            </div>
            <div className="home-request-states">
              <RecentStatus value={row.status} />
              {fresh && <span className="badge" data-tone="new">Nueva</span>}
            </div>
          </div>
        ) : (
          <>
            <div className="request-top">
              {flow && <span className="request-type">{flowName[flow]}</span>}
              <CollectionStatus value={row.status} />
              {fresh && <span className="badge" data-tone="new">Nueva</span>}
            </div>
            <h3 className="request-title">{material}</h3>
            {visit && showVisitInSummary ? (
              <p className="request-appointment">
                <CalendarDays size={16} aria-hidden="true" />
                <span>Visita: <strong><time dateTime={appointment.scheduled_at}>{visit}</time></strong></span>
              </p>
            ) : (
              date && <p className="request-date muted">Creada el <time dateTime={row.created_at}>{date}</time></p>
            )}
          </>
        )}
        <button type="button" className="request-toggle" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen((v) => !v)}>
          {open ? "Ocultar detalle" : "Ver detalle"}
          <ChevronDown size={18} aria-hidden="true" />
        </button>
        <div id={detailId} className="request-detail" hidden={!open}>
          <dl className="detail-list">
            {recent && <div><dt>Identificador</dt><dd className="data">{row.id}</dd></div>}
            <div><dt>Dirección</dt><dd>{row.address}</dd></div>
            {availability && <div><dt>Disponibilidad</dt><dd>{availability}</dd></div>}
            {row.notes && <div><dt>Observaciones</dt><dd>{row.notes}</dd></div>}
            {appointment && <div><dt>Responsable</dt><dd>{appointment.responsible_name}</dd></div>}
            {visit && (showVisitInSummary
              ? date && <div><dt>Creada</dt><dd>{date}</dd></div>
              : <div><dt>Visita</dt><dd><time dateTime={appointment.scheduled_at}>{visit}</time></dd></div>)}
            {!appointment && ["received", "under_review"].includes(row.status) && (
              <div><dt>Cita</dt><dd>Aún sin programar. Te avisaremos cuando el colectivo la confirme.</dd></div>
            )}
          </dl>
          {token && <RequestTimeline id={row.id} token={token} />}
        </div>
      </div>
    </article>
  );
}
