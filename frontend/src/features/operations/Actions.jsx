import { useState } from "react";
import { CalendarDays, Check, Search, X } from "../../components/icons.jsx";
import { Field } from "../../components/Field.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog.jsx";
import { NumberInput, Select, TextInput, Textarea } from "../../components/ui/inputs.jsx";
import { friendlyError } from "../../services/errors.js";
import { formatDateTime, toBogotaInput, toBogotaTimestamp } from "../../utils/dateTime.js";

const CHANNELS = { llamada: "Llamada", whatsapp: "WhatsApp", mensaje: "Mensaje de texto", en_persona: "En persona", planilla: "Planilla firmada" };

// Acciones de la coordinadora sobre una solicitud de su colectivo:
// revisar, programar (fecha, hora y recolector) y registrar la recogida.
// El registro lo hace la coordinadora con lo que le comunicó el recolector.
function Actions({ row, perform, workers = [], materials = [] }) {
  const [mode, setMode] = useState("");
  const [values, setValues] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  if (!["recibida", "revision", "programada"].includes(row.estado)) return null;
  const scheduled = row.estado === "programada";
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }));
  const workerName = (id) => workers.find((w) => String(w.id) === String(id))?.full_name || row.nombre_responsable || "el recolector";
  const now = toBogotaInput(Date.now());
  const dateField = mode === "cerrar" ? values.recogida_en : values.cita;
  const timestamp = toBogotaTimestamp(dateField);
  const displayDate = formatDateTime(timestamp);

  function open(next) {
    setError("");
    setMode(next);
    setValues(next === "cerrar"
      ? { recolector: row.responsable || "", recogida_en: now, material: "", kilos: "", resultado: "total", canal: "llamada", detalle: "", observaciones: "" }
      : { cita: scheduled ? toBogotaInput(row.cita) : "", motivo: "", responsable: "" });
  }

  function closeBody() {
    const constancia = CHANNELS[values.canal] + (values.detalle.trim() ? `: ${values.detalle.trim()}` : "");
    return {
      material: values.material, kilos: values.kilos, resultado: values.resultado,
      recogida_en: timestamp, recolector: values.recolector || undefined, constancia,
      ...(values.observaciones.trim() ? { observaciones: values.observaciones.trim() } : {}),
    };
  }

  async function send() {
    setBusy(true);
    setError("");
    const body = mode === "programar"
      ? { cita: timestamp, responsable: values.responsable, ...(scheduled ? { motivo: values.motivo } : {}) }
      : closeBody();
    try {
      await perform(`/recolecciones/${row.id}/${mode}`, body, mode === "cerrar" ? "Recogida registrada. Los puntos se acreditaron al vecino." : scheduled ? "Visita reprogramada." : "Visita agendada.");
      setConfirming(false);
      setMode("");
    } catch (err) {
      setConfirming(false);
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  function submit(e) {
    e.preventDefault();
    if (!e.currentTarget.reportValidity()) return;
    if (!timestamp) {
      setError("Indica una fecha y hora válidas de Colombia.");
      return;
    }
    if (mode === "cerrar") setConfirming(true);
    else send();
  }

  return (
    <div className="ops-actions">
      {!mode && (
        <>
          {error && <Alert tone="error">{error}</Alert>}
          {!workers.length && !scheduled && <Alert tone="warning">No hay recolectores activos en tu colectivo. Agrégalos en «Integrantes» para poder programar.</Alert>}
          {scheduled && !materials.length && <Alert tone="warning">No hay materiales con una regla de puntos vigente. Para registrar la recogida, la administración debe configurar el catálogo.</Alert>}
          <div className="btn-group">
            {row.estado === "recibida" && (
              <Button variant="secondary" size="lg" icon={Search} loading={busy} onClick={async () => {
                setBusy(true);
                try { await perform(`/recolecciones/${row.id}/revisar`, {}, "Solicitud marcada en revisión."); }
                catch (err) { setError(friendlyError(err)); }
                finally { setBusy(false); }
              }}>Marcar en revisión</Button>
            )}
            <Button variant={scheduled ? "secondary" : "primary"} size="lg" icon={CalendarDays} disabled={!workers.length} onClick={() => open("programar")}>
              {scheduled ? "Reprogramar visita" : "Agendar visita"}
            </Button>
            {scheduled && (
              <Button size="lg" icon={Check} disabled={!materials.length} onClick={() => open("cerrar")}>Registrar recogida</Button>
            )}
          </div>
        </>
      )}
      {mode && (
        <form className="ops-form form-stack enter" onSubmit={submit}>
          <h4 className="ops-form-title">
            {mode === "cerrar" ? "Registrar recogida" : scheduled ? "Reprogramar visita" : "Agendar visita"}
          </h4>
          {mode === "cerrar" && (
            <p className="muted">Anota el resultado que te comunicó el recolector. Quedará registrado a tu nombre como coordinadora.</p>
          )}
          <fieldset className="plain form-grid two" disabled={busy}>
            {mode === "programar" ? (
              <>
                <Field label={row.flujo === "reciclaje" ? "Asignar reciclador" : "Asignar huertero"}>
                  <Select required value={values.responsable} onChange={set("responsable")}>
                    <option value="">Selecciona una persona</option>
                    {workers.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
                  </Select>
                </Field>
                <Field label="Fecha y hora (Barranquilla)" hint={displayDate || "Debe ser posterior a este momento."}>
                  <TextInput type="datetime-local" required min={now} value={values.cita} onChange={set("cita")} />
                </Field>
                {scheduled && (
                  <Field label="Motivo del cambio">
                    <TextInput required maxLength={500} value={values.motivo} onChange={set("motivo")} />
                  </Field>
                )}
              </>
            ) : (
              <>
                <Field label="¿Quién hizo la recogida?">
                  <Select required value={values.recolector} onChange={set("recolector")}>
                    <option value="">Selecciona una persona</option>
                    {workers.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
                  </Select>
                </Field>
                <Field label="Fecha y hora real de la recogida" hint={displayDate || "No puede ser posterior a este momento."}>
                  <TextInput type="datetime-local" required max={now} value={values.recogida_en} onChange={set("recogida_en")} />
                </Field>
                <Field label="Material entregado" className="span-2" hint={row.solicitud?.material ? `Declarado por el vecino: ${row.solicitud.material}` : undefined}>
                  <Select required value={values.material} onChange={set("material")}>
                    <option value="">Selecciona el material del catálogo</option>
                    {materials.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
                  </Select>
                </Field>
                <Field label="Kilos aceptados" hint="Usa punto para decimales. Ej.: 2.5">
                  <NumberInput required min="0.001" max="10000" step="0.001" value={values.kilos} onChange={set("kilos")} />
                </Field>
                <Field label="Resultado">
                  <Select value={values.resultado} onChange={set("resultado")}>
                    <option value="total">Total</option>
                    <option value="parcial">Parcial</option>
                  </Select>
                </Field>
                <Field label="¿Cómo te informó el resultado?">
                  <Select value={values.canal} onChange={set("canal")}>
                    {Object.entries(CHANNELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </Select>
                </Field>
                <Field label="Detalle de la confirmación" optional>
                  <TextInput maxLength={200} value={values.detalle} onChange={set("detalle")} placeholder="Ej.: 3 bolsas entregadas" />
                </Field>
                <Field label="Observaciones" optional className="span-2">
                  <Textarea maxLength={1000} rows={2} value={values.observaciones} onChange={set("observaciones")} />
                </Field>
              </>
            )}
          </fieldset>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="btn-group">
            <Button variant="secondary" size="lg" icon={X} disabled={busy} onClick={() => setMode("")}>Volver</Button>
            <Button type="submit" size="lg" loading={busy && mode === "programar"} icon={Check}>
              {mode === "cerrar" ? "Revisar registro" : "Confirmar cita"}
            </Button>
          </div>
        </form>
      )}
      <ConfirmDialog
        open={confirming}
        title="¿Registrar esta recogida?"
        confirmLabel="Sí, registrar"
        busy={busy}
        onCancel={() => setConfirming(false)}
        onConfirm={send}
      >
        {mode === "cerrar" && values.material && (
          <dl className="summary">
            <div className="summary-row"><dt>Recolector</dt><dd>{workerName(values.recolector)}</dd></div>
            <div className="summary-row"><dt>Recogida real</dt><dd>{displayDate}</dd></div>
            <div className="summary-row"><dt>Material</dt><dd>{materials.find((item) => item.code === values.material)?.name || values.material}</dd></div>
            <div className="summary-row"><dt>Kilos</dt><dd className="data">{values.kilos}</dd></div>
            <div className="summary-row"><dt>Resultado</dt><dd>{values.resultado === "total" ? "Total" : "Parcial"}</dd></div>
            <div className="summary-row"><dt>Constancia</dt><dd>{closeBody().constancia}</dd></div>
          </dl>
        )}
        <p className="muted">Se registra la entrega y se acreditan los puntos una sola vez. No se puede deshacer desde aquí.</p>
      </ConfirmDialog>
    </div>
  );
}

export { Actions };
