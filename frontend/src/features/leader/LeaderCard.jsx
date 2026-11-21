import { CalendarDays, Clock3, House, MapPin, MessageSquare, Phone, Scale, UserRound } from "../../components/icons.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { formatAvailability, formatWhen } from "../../utils/format.js";
import { formatPhone } from "../auth/validation.js";
import { Actions } from "../operations/Actions.jsx";
import { RequestHistory } from "../operations/RequestHistory.jsx";
import { WorkerNotice } from "../operations/WorkerNotice.jsx";

// Tarjeta operativa para tableta: letra grande, datos en filas con icono y
// acciones táctiles amplias. Solo muestra datos de la bandeja del colectivo.
export function LeaderCard({ row, perform, workers = [], materials = [], token, id }) {
  const s = row.solicitud;
  const e = row.entrega;
  const title = s?.material || e?.material || "Entrega directa";
  const appointment = formatWhen(row.cita);
  const collected = formatWhen(e?.recogida_en);
  const availability = formatAvailability(s?.disponibilidad);
  const materialName = (code) => materials.find((m) => m.code === code)?.name || code;
  const workerName = (id) => workers.find((w) => String(w.id) === String(id))?.full_name
    || (String(id) === String(row.responsable) && row.nombre_responsable) || "Integrante del colectivo";
  const facts = [
    s?.direccion && [MapPin, "Dirección", s.direccion],
    s?.contacto && [Phone, "Contacto", <a href={`tel:+57${s.contacto}`} className="data">{formatPhone(s.contacto)}</a>],
    availability && [Clock3, "Disponibilidad", availability],
    s?.generador && [House, "Generador", s.generador === "unidad_productiva" ? "Unidad productiva" : "Hogar"],
    s?.observaciones && [MessageSquare, "Observaciones", s.observaciones],
    appointment && [CalendarDays, "Cita", <strong>{appointment}</strong>],
    row.cita && [UserRound, "Responsable", row.nombre_responsable || "Asignado por turno"],
    e && [Scale, "Entregado", `${materialName(e.material)} · ${Number(e.kilos).toLocaleString("es-CO")} kg · ${e.resultado === "total" ? "Total" : "Parcial"}`],
    collected && [CalendarDays, "Recogida real", collected],
    e?.recolector && [UserRound, "La realizó", workerName(e.recolector)],
    e?.constancia && [MessageSquare, "Constancia (registrada por la coordinadora)", e.constancia],
    e?.observaciones && [MessageSquare, "Observaciones del cierre", e.observaciones],
  ].filter(Boolean);
  return (
    <article className="ops-card" id={id} aria-label={`Detalle: ${title}`}>
      <div className="ops-card-top">
        <CollectionStatus value={row.estado} />
        <span className="ops-reference data">#{row.id.slice(0, 8)}</span>
      </div>
      <h2 className="ops-title">{title}</h2>
      <dl className="ops-facts">
        {facts.map(([Icon, label, value]) => (
          <div key={label}>
            <dt><Icon size={20} aria-hidden="true" />{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <Actions row={row} perform={perform} workers={workers} materials={materials} />
      <WorkerNotice row={row} perform={perform} />
      {token && <RequestHistory id={row.id} token={token} />}
    </article>
  );
}
