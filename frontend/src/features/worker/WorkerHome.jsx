import { useState } from "react";
import { CalendarDays, ChevronDown, CircleCheck, Clock3, LogOut, MapPin, MessageSquare, Phone, Recycle, Sprout } from "../../components/icons.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { Tabs } from "../../components/ui/Tabs.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { formatAvailability, formatDateTime } from "../../utils/dateTime.js";
import { formatPhone } from "../auth/validation.js";
import { RequestHistory } from "../operations/RequestHistory.jsx";
import { RecordCollection } from "./RecordCollection.jsx";

// Acceso operativo de huerteros y recicladores (móvil primero, dispositivos
// compartidos). Solo muestra las recogidas asignadas a su integrante; FastAPI
// lo comprueba en cada petición. Sin datos guardados en el dispositivo.
export function WorkerHome({ user, data, perform, token, logout, busy }) {
  const [tab, setTab] = useState("pendientes");
  const [recording, setRecording] = useState(null);
  const recycling = user.collective_flow === "reciclaje";
  const Icon = recycling ? Recycle : Sprout;
  const rows = data?.rows || [];
  const pending = rows.filter((r) => r.estado === "programada");
  const done = rows.filter((r) => r.estado === "recolectada");
  const shown = tab === "pendientes" ? pending : done;

  return (
    <div className="page view leader worker">
      <section className="ops-hero worker-hero">
        <span className="ops-hero-icon" aria-hidden="true"><Icon size={30} /></span>
        <div>
          <p>{recycling ? "Reciclables" : "Orgánicos"}</p>
          <h1>Mis recogidas</h1>
        </div>
        {/* Cierre de sesión visible para dispositivos compartidos */}
        <Button variant="secondary" size="lg" icon={LogOut} loading={busy} onClick={logout} className="worker-logout">Cerrar sesión</Button>
      </section>

      {!data ? <Loading>Cargando tus asignaciones…</Loading> : (
        <>
          <Tabs id="worker" label="Mis recogidas" value={tab} onChange={(next) => { setTab(next); setRecording(null); }} items={[
            { id: "pendientes", label: "Por realizar", icon: CalendarDays, count: pending.length },
            { id: "realizadas", label: "Realizadas", icon: CircleCheck, count: done.length },
          ]} />
          <section id="worker-panel" role="tabpanel" aria-labelledby={`worker-tab-${tab}`} className="tabpanel" key={tab}>
            {!shown.length ? (
              <EmptyState icon={CalendarDays} title={tab === "pendientes" ? "No tienes recogidas por atender" : "Aún no has registrado recogidas"}>
                {tab === "pendientes" ? "Cuando la coordinación te asigne una visita, aparecerá aquí." : "Las recogidas que registres quedarán aquí."}
              </EmptyState>
            ) : (
              <div className="ops-grid">
                {shown.map((r) => {
                  const s = r.solicitud;
                  const e = r.entrega;
                  return (
                    <article key={r.id} className="ops-card" aria-label={`Recogida ${s?.material || ""}`}>
                      <div className="ops-card-top">
                        <CollectionStatus value={r.estado} />
                        <span className="data muted">#{String(r.id).slice(0, 8)}</span>
                      </div>
                      <h2 className="ops-title">{s?.material || e?.material}</h2>
                      <dl className="ops-facts">
                        {r.cita && <div><dt><CalendarDays size={20} />Fecha y hora</dt><dd><strong>{formatDateTime(r.cita)}</strong></dd></div>}
                        {s?.direccion && <div><dt><MapPin size={20} />Dirección</dt><dd>{s.direccion}</dd></div>}
                      </dl>
                      <details className="worker-detail">
                        <summary className="detail-trigger">Ver recogida <ChevronDown size={18} aria-hidden="true" /></summary>
                        <div className="worker-detail-body">
                          <dl className="ops-facts">
                            {s?.contacto && <div><dt><Phone size={20} />Contacto</dt><dd><a href={`tel:+57${s.contacto}`} className="data">{formatPhone(s.contacto)}</a></dd></div>}
                            {s?.disponibilidad && <div><dt><Clock3 size={20} />Disponibilidad</dt><dd>{formatAvailability(s.disponibilidad)}</dd></div>}
                            {s?.observaciones && <div><dt><MessageSquare size={20} />Indicaciones</dt><dd>{s.observaciones}</dd></div>}
                            {e && <div><dt><CircleCheck size={20} />Registrado</dt><dd>{e.material} · {Number(e.kilos).toLocaleString("es-CO")} {e.unidad || "kg"} · {e.resultado === "total" ? "Total" : "Parcial"}{e.recogida_en ? ` · ${formatDateTime(e.recogida_en)}` : ""}</dd></div>}
                          </dl>
                          {r.estado === "programada" && (recording === r.id ? (
                            <RecordCollection row={r} materials={data.materials || []} perform={perform} onDone={() => setRecording(null)} />
                          ) : (
                            <Button size="lg" block icon={CircleCheck} onClick={() => setRecording(r.id)}>Registrar recolección</Button>
                          ))}
                          <RequestHistory id={r.id} token={token} />
                        </div>
                      </details>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
