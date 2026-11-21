import { useState } from "react";
import { Check, X } from "../../components/icons.jsx";
import { Field } from "../../components/Field.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog.jsx";
import { NumberInput, Select, Textarea, TextInput } from "../../components/ui/inputs.jsx";
import { friendlyError } from "../../services/errors.js";
import { formatDateTime, toBogotaInput, toBogotaTimestamp } from "../../utils/dateTime.js";

// El recolector asignado registra la recolección (POST /recolecciones/{id}/cerrar).
// FastAPI valida que la solicitud le esté asignada; no puede cambiar fecha,
// responsable ni puntos. Los puntos se calculan en el servidor con la regla vigente.
export function RecordCollection({ row, materials, perform, onDone }) {
  const now = toBogotaInput(Date.now());
  const [values, setValues] = useState({ recogida_en: now, material: "", kilos: "", resultado: "total", observaciones: "" });
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }));
  const materialName = materials.find((m) => m.code === values.material)?.name || values.material;

  async function send() {
    setBusy(true);
    setError("");
    try {
      await perform(`/recolecciones/${row.id}/cerrar`, {
        material: values.material, kilos: values.kilos, unidad: "kg", resultado: values.resultado,
        recogida_en: toBogotaTimestamp(values.recogida_en),
        ...(values.observaciones.trim() ? { observaciones: values.observaciones.trim() } : {}),
      }, "Recolección registrada. Los puntos se acreditaron al solicitante.");
      setConfirming(false);
      onDone();
    } catch (err) {
      setConfirming(false);
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  if (!materials.length)
    return <Alert tone="warning">Aún no hay materiales con regla de puntos configurada. Avisa a la coordinación antes de registrar.</Alert>;

  return (
    <form className="ops-form form-stack enter" onSubmit={(e) => { e.preventDefault(); if (e.currentTarget.reportValidity()) setConfirming(true); }}>
      <h3 className="ops-form-title">Registrar recolección</h3>
      <fieldset className="plain form-stack" disabled={busy}>
        <Field label="Fecha y hora en que recogiste" hint="No puede ser posterior a este momento.">
          <TextInput type="datetime-local" required max={now} value={values.recogida_en} onChange={set("recogida_en")} />
        </Field>
        <Field label="Material entregado">
          <Select required value={values.material} onChange={set("material")}>
            <option value="">Selecciona el material</option>
            {materials.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}
          </Select>
        </Field>
        <Field label="Cantidad (kilogramos)" hint="Usa punto para decimales. Ej.: 2.5">
          <NumberInput required min="0.001" max="10000" step="0.001" value={values.kilos} onChange={set("kilos")} />
        </Field>
        <Field label="Resultado">
          <Select value={values.resultado} onChange={set("resultado")}>
            <option value="total">Se recogió todo</option>
            <option value="parcial">Se recogió una parte</option>
          </Select>
        </Field>
        <Field label="Observaciones" optional>
          <Textarea rows={2} maxLength={1000} value={values.observaciones} onChange={set("observaciones")} />
        </Field>
      </fieldset>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="btn-group">
        <Button variant="secondary" size="lg" icon={X} disabled={busy} onClick={onDone}>Volver</Button>
        <Button type="submit" size="lg" icon={Check}>Revisar registro</Button>
      </div>
      <ConfirmDialog open={confirming} title="¿Registrar esta recolección?" confirmLabel="Sí, registrar" busy={busy}
        onCancel={() => setConfirming(false)} onConfirm={send}>
        <dl className="summary">
          <div className="summary-row"><dt>Recogida</dt><dd>{formatDateTime(toBogotaTimestamp(values.recogida_en))}</dd></div>
          <div className="summary-row"><dt>Material</dt><dd>{materialName}</dd></div>
          <div className="summary-row"><dt>Cantidad</dt><dd className="data">{values.kilos} kg</dd></div>
          <div className="summary-row"><dt>Resultado</dt><dd>{values.resultado === "total" ? "Total" : "Parcial"}</dd></div>
        </dl>
        <p className="muted">Quedará registrada a tu nombre y no se puede repetir.</p>
      </ConfirmDialog>
    </form>
  );
}
