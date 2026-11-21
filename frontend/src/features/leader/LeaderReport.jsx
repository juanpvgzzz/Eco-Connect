import { useEffect, useState } from "react";
import { Field } from "../../components/Field.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { TextInput } from "../../components/ui/inputs.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { request } from "../../services/api.js";
import { formatShortDate, toBogotaTimestamp } from "../../utils/dateTime.js";
import { nameOf } from "../../utils/format.js";
import { addDays, todayKey } from "../calendar/week.js";

const STATUSES = ["recibida", "revision", "programada", "recolectada", "cancelada"];
const FLOW_LABELS = { huerta: "Residuos orgánicos", reciclaje: "Residuos reciclables" };

export function LeaderReport({ token }) {
  const [period, setPeriod] = useState(() => {
    const end = todayKey();
    return { start: addDays(end, -29), end };
  });
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [dateError, setDateError] = useState("");

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({
      desde: toBogotaTimestamp(`${period.start}T00:00`),
      // La API excluye el límite final. Se incluye todo el último día elegido.
      hasta: toBogotaTimestamp(`${addDays(period.end, 1)}T00:00`),
    });
    request(`/recolecciones/resumen?${params}`, { token })
      .then((summary) => { if (active) setData(summary); })
      .catch((cause) => { if (active) setError(cause.message || "No se pudo consultar el resumen."); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [period, token]);

  function consult(event) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const start = values.get("start");
    const end = values.get("end");
    if (start > end) {
      setDateError("La fecha final debe ser igual o posterior a la inicial.");
      return;
    }
    setDateError("");
    setError("");
    setData(null);
    setBusy(true);
    setPeriod({ start, end });
  }

  return <Card as="section" className="leader-report" aria-labelledby="ops-title">
    <p>Solicitudes ingresadas entre las fechas elegidas, con su estado actual. Se incluyen ambos días en hora de Barranquilla.</p>
    <form className="leader-report-filters" onSubmit={consult} onChange={() => setDateError("")}>
      <Field label="Fecha inicial"><TextInput name="start" type="date" required defaultValue={period.start} /></Field>
      <Field label="Fecha final" error={dateError}><TextInput name="end" type="date" required defaultValue={period.end} /></Field>
      <Button type="submit" size="lg" loading={busy}>Consultar resumen</Button>
    </form>
    {error && <Alert tone="error" title="No se pudo consultar el resumen">{error}</Alert>}
    {busy && <Loading>Consultando solicitudes…</Loading>}
    <div aria-live="polite">
      {!busy && data && <>
        <h2>{FLOW_LABELS[data.flujo]}</h2>
        <p>Del {formatShortDate(period.start)} al {formatShortDate(period.end)}</p>
        <dl className="summary">
          {STATUSES.map((status) => <div className="summary-row" key={status}>
            <dt>{nameOf[status]}</dt><dd className="data">{data.conteos[status]}</dd>
          </div>)}
        </dl>
      </>}
    </div>
  </Card>;
}
