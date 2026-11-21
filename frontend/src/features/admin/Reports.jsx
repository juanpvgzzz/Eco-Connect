import { useEffect, useState } from "react";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { Field } from "../../components/Field.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { TextInput } from "../../components/ui/inputs.jsx";
import { request } from "../../services/api.js";
import { formatDateTime, toBogotaInput, toBogotaTimestamp } from "../../utils/dateTime.js";

const STATUS_ORDER = ["recibida", "revision", "programada", "recolectada", "cancelada"];
const STATUS_LABELS = { recibida: "Recibida", revision: "En revisión", programada: "Programada", recolectada: "Recolectada", cancelada: "Cancelada" };
const FLOWS = [["huerta", "Residuos orgánicos"], ["reciclaje", "Residuos reciclables"]];

export function Reports({ token }) {
  const now = new Date();
  const startDefault = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const [start, setStart] = useState(() => toBogotaInput(startDefault));
  const [end, setEnd] = useState(() => toBogotaInput(now));
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(from = start, until = end) {
    setBusy(true);
    setError("");
    try {
      const desde = toBogotaTimestamp(from);
      const hasta = toBogotaTimestamp(until);
      if (!desde || !hasta) throw new Error("Indica fechas y horas válidas para el período.");
      const params = new URLSearchParams({ desde, hasta });
      setData(await request(`/accounts/admin/reports?${params}`, { token }));
    } catch (cause) { setError(cause.message || "No se pudo cargar el resumen."); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  return <section className="admin-reports" aria-labelledby="reports-title">
    <h2 id="reports-title">Resumen operativo</h2>
    <p className="muted">Los conteos se calculan en PostgreSQL para el intervalo seleccionado (hora de Barranquilla).</p>
    <form className="admin-report-filters" onSubmit={(event) => { event.preventDefault(); load(); }}>
      <Field label="Desde" hint={formatDateTime(start)}><TextInput type="datetime-local" required value={start} onChange={(event) => setStart(event.target.value)} /></Field>
      <Field label="Hasta (exclusivo)" hint={formatDateTime(end)}><TextInput type="datetime-local" required value={end} onChange={(event) => setEnd(event.target.value)} /></Field>
      <Button type="submit" size="lg" loading={busy}>Consultar</Button>
    </form>
    {error && <Alert tone="error">{error}</Alert>}
    {busy && !data ? <Loading>Consultando datos…</Loading> : data && <>
      <div className="ops-grid">
        {FLOWS.map(([flow, label]) => <Card as="article" key={flow} className="report-flow">
          <h3>{label}</h3>
          <dl>{STATUS_ORDER.map((status) => <div key={status}><dt>{STATUS_LABELS[status]}</dt><dd className="data">{data.solicitudes?.[flow]?.[status] ?? 0}</dd></div>)}</dl>
        </Card>)}
      </div>
      <div className="report-totals">
        <Card><strong className="data">{data.recogidas_completadas}</strong><span> recogidas completadas en el período</span></Card>
        <Card><strong className="data">{data.puntos_acreditados}</strong><span> puntos acreditados en el período</span></Card>
      </div>
    </>}
  </section>;
}
