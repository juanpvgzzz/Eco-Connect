import { useMemo, useState } from "react";
import { CalendarDays, ChevronDown, ChevronRight, CircleCheck, CircleX, ClipboardList, Clock3, Inbox, MapPin, Recycle, Search, Sprout } from "../../components/icons.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Tabs } from "../../components/ui/Tabs.jsx";
import { ErrorBoundary } from "../../components/ErrorBoundary.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { useMediaQuery } from "../../hooks/useMediaQuery.js";
import { formatAvailability, formatWhen, stageOf } from "../../utils/format.js";
import { NoticeList } from "../notices/NoticeList.jsx";
import { leaderNotice } from "../notices/model.js";
import { LeaderCard } from "./LeaderCard.jsx";
import { LeaderReport } from "./LeaderReport.jsx";
import { MembersPanel } from "./MembersPanel.jsx";
import { WeekCalendar } from "../calendar/WeekCalendar.jsx";

const STAGES = [
  { id: "pending", label: "Pendientes", icon: Inbox, hint: "Solicitudes nuevas. Revísalas o agenda una visita." },
  { id: "review", label: "Revisadas", icon: Search, hint: "Solicitudes en revisión, listas para programar." },
  { id: "scheduled", label: "Programadas", icon: CalendarDays, hint: "Visitas con fecha. Registra la recogida al terminar." },
  { id: "done", label: "Completadas", icon: CircleCheck, hint: "Recogidas registradas." },
  { id: "cancelled", label: "Canceladas", icon: CircleX, hint: "Solicitudes canceladas." },
];
const stage = (row) => stageOf[row.estado] || "pending";

// Panel de coordinadoras (tableta primero). Filtros grandes por estado con
// contador, bandeja y detalle. Tableta horizontal/escritorio: lista a la
// izquierda y detalle a la derecha. Tableta vertical/móvil: una columna con
// el detalle desplegado bajo la solicitud elegida.
export function LeaderBoard({ data, view, setView, perform, token, flow, onMembersChanged }) {
  const [tab, setTab] = useState("pending");
  const [selected, setSelected] = useState(null);
  const wide = useMediaQuery("(min-width: 1024px)");
  const rows = data?.rows || [];
  const recycling = flow === "reciclaje";
  const TeamIcon = recycling ? Recycle : Sprout;
  const team = recycling ? "Colectivo de reciclaje" : "Huerta comunitaria";
  const title = recycling ? "Solicitudes de reciclables" : "Solicitudes de orgánicos";
  const viewTitle = { calendario: "Calendario", integrantes: "Integrantes", avisos: "Avisos", reportes: "Resumen por período" }[view] || title;
  const counts = useMemo(() => Object.fromEntries(STAGES.map((s) => [s.id, rows.filter((r) => stage(r) === s.id).length])), [rows]);
  const notices = useMemo(() => (data?.notices || []).map((n, i) => leaderNotice(n, i, rows)), [data, rows]);
  const current = STAGES.find((s) => s.id === tab);
  const visible = rows.filter((r) => stage(r) === tab);
  // En pantalla ancha siempre hay una solicitud en el panel de detalle.
  const active = visible.find((r) => r.id === selected) || (wide ? visible[0] : null);

  const detail = (row) => (
    <LeaderCard
      key={row.id}
      id={`detalle-${row.id}`}
      row={row}
      perform={perform}
      token={token}
      workers={data.workers || []}
      materials={data.materials || []}
    />
  );

  return (
    <div className="page view leader">
      <section className="ops-hero" aria-labelledby="ops-title">
        <span className="ops-hero-icon" aria-hidden="true"><TeamIcon size={30} /></span>
        <div>
          <p>{team}</p>
          <h1 id="ops-title">{viewTitle}</h1>
        </div>
      </section>

      {view === "reportes" ? (
        <LeaderReport token={token} />
      ) : !data ? (
        <Loading>Cargando la bandeja…</Loading>
      ) : view === "calendario" ? (
        <WeekCalendar token={token} onOpen={(item) => {
          setTab(stage(item));
          setSelected(item.id);
          setView("inicio");
          requestAnimationFrame(() => document.getElementById(`detalle-${item.id}`)?.scrollIntoView({ block: "start" }));
        }} />
      ) : view === "integrantes" ? (
        <MembersPanel token={token} onChanged={onMembersChanged} />
      ) : view === "avisos" ? (
        <NoticeList notices={notices} />
      ) : (
        <>
          <Tabs
            id="ops"
            label="Estados de las solicitudes"
            value={tab}
            onChange={(next) => {
              setTab(next);
              setSelected(null);
            }}
            items={STAGES.map((s) => ({ id: s.id, label: s.label, icon: s.icon, count: counts[s.id] }))}
          />
          <section id="ops-panel" role="tabpanel" aria-labelledby={`ops-tab-${tab}`} className="tabpanel" key={tab} tabIndex={-1}>
            <ErrorBoundary message="Esta sección no se pudo mostrar. Las demás siguen disponibles.">
                <>
                  <p className="ops-hint">{current.hint}</p>
                  {!visible.length ? (
                    <EmptyState icon={ClipboardList} title={`No hay solicitudes ${current.label.toLowerCase()}`}>
                      Cuando lleguen, aparecerán aquí.
                    </EmptyState>
                  ) : (
                    <div className="ops-split">
                      <ul className="ops-list" aria-label={`Solicitudes ${current.label.toLowerCase()}`}>
                        {visible.map((row) => {
                          const isActive = active?.id === row.id;
                          const s = row.solicitud;
                          const appointment = formatWhen(row.cita);
                          const availability = !appointment && formatAvailability(s?.disponibilidad);
                          return (
                            <li key={row.id}>
                              <button
                                type="button"
                                className="ops-item"
                                aria-expanded={wide ? undefined : isActive}
                                aria-current={wide && isActive ? "true" : undefined}
                                aria-controls={isActive ? `detalle-${row.id}` : undefined}
                                onClick={() => setSelected(!wide && isActive ? null : row.id)}
                              >
                                <span className="ops-item-main">
                                  <span className="ops-item-reference data">#{row.id.slice(0, 8)}{s?.generador ? ` · ${s.generador === "unidad_productiva" ? "Unidad productiva" : "Hogar"}` : ""}</span>
                                  <span className="ops-item-title">{s?.material || row.entrega?.material || "Entrega directa"}</span>
                                  {s?.direccion && <span className="ops-item-meta"><MapPin size={16} />{s.direccion.split(",")[0]}</span>}
                                  {appointment && <span className="ops-item-meta"><CalendarDays size={16} />{appointment}</span>}
                                  {availability && <span className="ops-item-meta"><Clock3 size={16} />{availability}</span>}
                                </span>
                                <span className="ops-item-side">
                                  <CollectionStatus value={row.estado} />
                                  <span className="ops-item-open">
                                    {isActive ? "Detalle" : "Ver solicitud"}
                                    {wide ? <ChevronRight size={18} /> : <ChevronDown size={18} className="ops-item-chevron" />}
                                  </span>
                                </span>
                              </button>
                              {!wide && isActive && <div className="ops-inline">{detail(row)}</div>}
                            </li>
                          );
                        })}
                      </ul>
                      {wide && active && <div className="ops-detail">{detail(active)}</div>}
                    </div>
                  )}
                </>
            </ErrorBoundary>
          </section>
        </>
      )}
    </div>
  );
}
