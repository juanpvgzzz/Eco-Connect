import { useState } from "react";
import { X } from "../../components/icons.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { CollectionStatus } from "../../components/CollectionStatus.jsx";
import { formatAvailability, formatDateTime } from "../../utils/dateTime.js";
import { WeekCalendar } from "./WeekCalendar.jsx";

// Calendario para administración: consulta ambos colectivos (o uno) y muestra
// el detalle en solo lectura. Las acciones siguen en el panel de cada coordinadora.
export function AdminCalendar({ token }) {
  const [item, setItem] = useState(null);
  const s = item?.solicitud;
  const facts = item && [
    ["Solicitud", <span className="data">{item.id}</span>],
    ["Colectivo", item.flujo === "reciclaje" ? "Recicladores (reciclables)" : "Huerteros (orgánicos)"],
    ["Estado", <CollectionStatus value={item.estado} />],
    ["Solicitada", formatDateTime(item.creada)],
    ["Programada", item.cita ? formatDateTime(item.cita) : "Sin programar"],
    ["Responsable", item.nombre_responsable || "Sin asignar"],
    ["Material", s?.material || item.material || item.entrega?.material],
    ["Dirección", s?.direccion],
    ["Disponibilidad", s?.disponibilidad && formatAvailability(s.disponibilidad)],
  ].filter(([, v]) => v);
  return (
    <div className="admin-calendar">
      {item && (
        <Card className="cal-detail enter" aria-labelledby="cal-detail-title">
          <div className="wizard-head">
            <h2 id="cal-detail-title">Detalle de la recogida</h2>
            <Button variant="ghost" icon={X} onClick={() => setItem(null)}>Cerrar detalle</Button>
          </div>
          <dl className="summary">
            {facts.map(([label, value]) => (
              <div className="summary-row" key={label}><dt>{label}</dt><dd>{value}</dd></div>
            ))}
          </dl>
          <p className="muted">Solo consulta. La programación y el registro los hace la coordinadora del colectivo.</p>
        </Card>
      )}
      <WeekCalendar token={token} flows={["huerta", "reciclaje"]} onOpen={(r) => { setItem(r); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
    </div>
  );
}
