import { useState } from "react";
import { History } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { formatDateTime } from "../../utils/dateTime.js";

const LABEL = {
  recibida: "Solicitud recibida", revision: "En revisión", programada: "Recogida programada",
  reprogramada: "Recogida reprogramada", visita_fallida: "Visita fallida", cancelada: "Solicitud cancelada",
  recolectada: "Recogida completada", puntos_acreditados: "Puntos acreditados",
};

// Historial de una solicitud propia (GET /community/collections/{id}/history):
// estados, cita confirmada, resultado y puntos. Sin datos de otras personas.
export function RequestTimeline({ id, token }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function toggle() {
    if (items) return setItems(null);
    setBusy(true);
    setError("");
    try {
      setItems(await request(`/community/collections/${id}/history`, { token }));
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ops-history">
      <Button variant="ghost" icon={History} loading={busy} aria-expanded={Boolean(items)} onClick={toggle}>
        {items ? "Ocultar historial" : "Ver historial"}
      </Button>
      {error && <Alert tone="error">{error}</Alert>}
      {items && (
        <ol className="history-list">
          {items.map((e, i) => {
            const appointment = formatDateTime(e.scheduled_at);
            const collected = formatDateTime(e.collected_at);
            const date = formatDateTime(e.at);
            return (
              <li key={i}>
                <strong>{LABEL[e.event] || e.event}</strong>
                {(appointment || e.responsible_name) && <span>{[appointment, e.responsible_name].filter(Boolean).join(" · ")}</span>}
                {e.event === "recolectada" && (
                  <span>
                    {e.result === "total" ? "Total" : e.result === "parcial" ? "Parcial" : e.result}
                    {e.kilos ? ` · ${e.kilos} kg` : ""}
                    {collected ? ` · Recogida el ${collected}` : ""}
                  </span>
                )}
                {e.points ? <span className="data">+{e.points} puntos</span> : null}
                {e.reason && e.event !== "recolectada" && <span>{e.reason}</span>}
                {date && <time className="muted data" dateTime={e.at}>{date}</time>}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
