import { useCallback, useEffect, useState } from "react";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { Field } from "../../components/Field.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { NumberInput, TextInput } from "../../components/ui/inputs.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { formatDate } from "../../utils/format.js";

const EMPTY = { material_code: "", material_name: "", points_per_kg: "", note: "" };

// Reglas de puntos: puntos = ⌊kilogramos × puntos por kg⌋ con la regla vigente del
// material al registrar la recolección. Los valores que define administración son
// provisionales: los documentos de FSD no establecen equivalencias oficiales.
export function PointRules({ token }) {
  const [rules, setRules] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const load = useCallback(() => request("/accounts/admin/point-rules", { token }).then(setRules)
    .catch((cause) => setError(friendlyError(cause))), [token]);
  useEffect(() => { load(); }, [load]);
  const set = (k) => (e) => setForm((v) => ({ ...v, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (!e.currentTarget.reportValidity()) return;
    setBusy(true);
    setError("");
    setSaved("");
    try {
      await request("/accounts/admin/point-rules", { token, body: { ...form, note: form.note.trim() || null } });
      setSaved(`Regla provisional guardada para ${form.material_name}. Reemplaza a la anterior desde ahora.`);
      setForm(EMPTY);
      await load();
    } catch (cause) {
      setError(friendlyError(cause));
    } finally {
      setBusy(false);
    }
  }

  return <section className="admin-point-rules" aria-labelledby="points-rules-title">
    <h2 id="points-rules-title">Reglas de puntos</h2>
    <Alert tone="warning" title="Valores provisionales">
      Puntos = kilogramos entregados × puntos por kilogramo (sin decimales), con la regla vigente al registrar la recolección.
      Estos valores no son equivalencias oficiales de la Fundación Santo Domingo y están sujetos a su validación.
    </Alert>
    <Card as="form" className="content-editor" onSubmit={submit}>
      <h3>Nueva regla vigente</h3>
      <div className="form-grid two">
        <Field label="Código del material" hint="Ej.: ORG-COCINA, PET. Si ya existe, se reemplaza su regla.">
          <TextInput required pattern="[A-Za-z0-9][A-Za-z0-9_\-]{0,39}" maxLength={40} value={form.material_code} onChange={set("material_code")} />
        </Field>
        <Field label="Nombre del material">
          <TextInput required minLength={2} maxLength={80} value={form.material_name} onChange={set("material_name")} />
        </Field>
        <Field label="Puntos por kilogramo">
          <NumberInput required min="0" max="10000" step="0.001" value={form.points_per_kg} onChange={set("points_per_kg")} />
        </Field>
        <Field label="Nota" optional hint="Ej.: valor de prueba pendiente de validar con FSD.">
          <TextInput maxLength={300} value={form.note} onChange={set("note")} />
        </Field>
      </div>
      {saved && <Alert tone="success">{saved}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      <div><Button type="submit" size="lg" loading={busy}>Guardar regla provisional</Button></div>
    </Card>
    {rules === null ? <Loading>Cargando reglas configuradas…</Loading> : rules.length ? <div className="ops-grid">{rules.map((rule) => {
      const active = new Date(rule.valid_from) <= new Date() && (!rule.valid_until || new Date(rule.valid_until) > new Date());
      return <Card as="article" key={rule.id} className="point-rule">
        <div className="admin-account-heading">
          <h3>{rule.material_name} <span className="muted data">({rule.material_code})</span></h3>
          <span className="badge" data-tone={active ? "success" : "muted"}>{active ? "Vigente" : "Histórica"}</span>
          {rule.provisional && <span className="badge" data-tone="new">Provisional</span>}
        </div>
        <p><strong className="data">{rule.points_per_kg}</strong> puntos por kilogramo</p>
        {rule.note && <p className="muted">{rule.note}</p>}
        <p className="muted">Vigencia: {formatDate(rule.valid_from) || "inicio no disponible"} – {rule.valid_until ? formatDate(rule.valid_until) || "fin no disponible" : "sin fecha de fin"}</p>
      </Card>;
    })}</div> : <Card><p>No hay reglas de puntos configuradas. Las recogidas no podrán registrarse con acreditación hasta definir al menos una.</p></Card>}
  </section>;
}
