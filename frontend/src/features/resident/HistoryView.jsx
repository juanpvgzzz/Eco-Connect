import { ArrowLeft } from "../../components/icons.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { RequestList } from "./RequestList.jsx";

// Historial: todas las solicitudes de la cuenta, de la más reciente a la más antigua.
export function HistoryView({ rows, appointments, freshId, onNew, onBack, token }) {
  return (
    <section className="subview enter" aria-labelledby="history-title">
      <div className="view-head">
        <div>
          <h1 id="history-title">Mis solicitudes</h1>
          <p className="muted">{rows.length === 1 ? "1 solicitud" : `${rows.length} solicitudes`}</p>
        </div>
        <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Inicio</Button>
      </div>
      <RequestList rows={rows} appointments={appointments} freshId={freshId} onNew={onNew} token={token} />
    </section>
  );
}
