import { ArrowLeft, LogOut } from "../../components/icons.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { formatPhone } from "../auth/validation.js";

const ROLE = { resident: "Vecino o vecina", business: "Unidad productiva", leader: "Coordinación de colectivo", admin: "Administración" };

// Datos de la cuenta tal como los devuelve GET /accounts/me (solo lectura).
export function Profile({ user, onBack, onLogout }) {
  const p = user.profile;
  return (
    <Card className="profile enter" aria-labelledby="profile-title">
      <div className="wizard-head">
        <h1 id="profile-title" className="wizard-title">Mi perfil</h1>
        <Button variant="ghost" icon={ArrowLeft} onClick={onBack}>Volver</Button>
      </div>
      <dl className="summary">
        <div className="summary-row"><dt>Nombre</dt><dd>{p.full_name}</dd></div>
        <div className="summary-row"><dt>Cédula</dt><dd className="data">{p.national_id}</dd></div>
        <div className="summary-row"><dt>Celular</dt><dd className="data">{formatPhone(p.phone)}</dd></div>
        <div className="summary-row"><dt>Dirección</dt><dd>{p.address}</dd></div>
        <div className="summary-row"><dt>Perfil</dt><dd>{ROLE[p.role] || p.role}</dd></div>
      </dl>
      <p className="muted">Por ahora los datos de la cuenta no se pueden editar desde la aplicación.</p>
      <Button variant="secondary" size="lg" icon={LogOut} onClick={onLogout}>Cerrar sesión</Button>
    </Card>
  );
}
