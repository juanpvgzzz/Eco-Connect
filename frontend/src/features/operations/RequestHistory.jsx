import { useState } from "react";
import { History } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { formatDate, nameOf } from "../../utils/format.js";

// Consultar historial (GET /recolecciones/{id}/historial), bajo demanda.
export function RequestHistory({ id, token }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function toggle() {
    if (items) return setItems(null);
    setBusy(true);
    setError("");
    try {
      setItems(await request(`/recolecciones/${id}/historial`, { token }));
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ops-history">
      <Button variant="ghost" icon={History} loading={busy} aria-expanded={Boolean(items)} onClick={toggle}>
        {items ? "Ocultar historial" : "Consultar historial"}
      </Button>
      {error && <Alert tone="error">{error}</Alert>}
      {items && (
        items.length ? (
          <ol className="history-list">
            {items.map((e, i) => {
              const appointment = formatDate(e.registro?.cita);
              const collected = formatDate(e.registro?.entrega?.recogida_en);
              const date = formatDate(e.fecha);
              return (
                <li key={e.id || i}>
                  <strong>{nameOf[e.evento] || e.evento}</strong>
                  {(appointment || e.registro?.nombre_responsable) && ["programada", "reprogramada"].includes(e.evento) && (
                    <span>{[appointment, e.registro?.nombre_responsable && `Responsable: ${e.registro.nombre_responsable}`].filter(Boolean).join(" · ")}</span>
                  )}
                  {e.evento === "recolectada" && e.registro?.entrega && (
                    <span>
                      {e.registro.entrega.material} · {e.registro.entrega.kilos} kg · {e.registro.entrega.resultado}
                      {e.registro.nombre_recolector ? ` · La realizó ${e.registro.nombre_recolector}` : ""}
                      {collected ? ` · Recogida el ${collected}` : ""}
                      {e.registro.entrega.constancia ? ` · Constancia: ${e.registro.entrega.constancia}` : ""}
                    </span>
                  )}
                  {e.evento === "puntos_acreditados" && <span className="data">+{e.registro?.puntos} puntos</span>}
                  {e.motivo && <span>{e.motivo}</span>}
                  {date && <time className="muted data" dateTime={e.fecha}>{date}</time>}
                </li>
              );
            })}
          </ol>
        ) : <p className="muted">Sin movimientos registrados.</p>
      )}
    </div>
  );
}
