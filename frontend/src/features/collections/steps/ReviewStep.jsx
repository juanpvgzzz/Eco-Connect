import { Alert } from "../../../components/ui/Alert.jsx";
import { Button } from "../../../components/ui/Button.jsx";
import { formatPhone } from "../../auth/validation.js";
import { WASTE_TYPES } from "../materials.js";

// Paso 3: resumen de lo que se enviará, con acceso directo a cada paso.
export function ReviewStep({ payload, goTo, residuo }) {
  const type = WASTE_TYPES[residuo];
  const Icon = type.icon;
  const rows = [
    ["Tipo de residuo", <span className="badge" data-tone={type.tone}><Icon size={14} aria-hidden="true" />{type.short}</span>, 0],
    ["Material", payload.material, 0],
    ["Dirección", payload.direccion, 1],
    ["Celular", <span className="data">{formatPhone(payload.contacto)}</span>, 1],
    ["Disponibilidad", payload.disponibilidad, 1],
    ["Observaciones", payload.observaciones || <span className="muted">Sin observaciones</span>, 1],
  ];
  return (
    <div className="form-stack">
      <p className="muted">Revisa los datos. Puedes cambiar cualquier parte antes de confirmar.</p>
      <dl className="summary">
        {rows.map(([label, value, step]) => (
          <div className="summary-row" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
            <Button variant="ghost" onClick={() => goTo(step)} aria-label={`Cambiar ${label.toLowerCase()}`}>Cambiar</Button>
          </div>
        ))}
      </dl>
      <Alert tone="info">
        Al confirmar, la solicitud llegará a <strong>{type.team}</strong>. Te avisaremos cuando programen la visita.
      </Alert>
    </div>
  );
}
