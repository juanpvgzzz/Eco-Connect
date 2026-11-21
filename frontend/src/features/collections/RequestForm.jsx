import { useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Send, X } from "../../components/icons.jsx";
import { sessionKey } from "../../utils/format.js";
import { newIdempotencyKey } from "../../utils/idempotency.js";
import { friendlyError } from "../../services/errors.js";
import { Card } from "../../components/ui/Card.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Stepper } from "../../components/ui/Stepper.jsx";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog.jsx";
import { REQUEST_STEPS, newDraft, readDraft, toPayload, validateStep, writeDraft } from "./requestModel.js";
import { WasteStep } from "./steps/WasteStep.jsx";
import { PlaceTimeStep } from "./steps/PlaceTimeStep.jsx";
import { ReviewStep } from "./steps/ReviewStep.jsx";

const ADDRESS_FIELDS = ["number", "cross", "plate", "manzana", "casa", "sector", "references", "custom"];

// Asistente "Solicitar recogida" en tres pasos.
// - El borrador sobrevive a una recarga (sessionStorage, sin datos sensibles).
// - La Idempotency-Key cambia solo si cambian los datos: un reintento del mismo
//   envío reutiliza la clave y FastAPI no duplica la solicitud.
function RequestForm({ user, onCreate, onCancel }) {
  const storageKey = sessionKey + ".request." + user.id;
  const [draft, setDraft] = useState(() => readDraft(storageKey) || newDraft(user));
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const lock = useRef(false);
  const bodyRef = useRef(null);
  const { form, step } = draft;

  function save(next) {
    writeDraft(storageKey, next);
    setDraft(next);
  }
  function update(changes) {
    save({ ...draft, key: newIdempotencyKey(), form: { ...form, ...changes } });
    // Quita solo los errores de lo que se acaba de corregir; el resto sigue visible.
    const touched = new Set(Object.keys(changes));
    if (touched.has("picks") || touched.has("detail")) touched.add("material");
    if (touched.has("address")) ADDRESS_FIELDS.forEach((k) => touched.add(k));
    setErrors((current) => Object.fromEntries(Object.entries(current).filter(([k]) => !touched.has(k))));
  }
  function goTo(index) {
    setErrors({});
    setError("");
    save({ ...draft, step: index });
    requestAnimationFrame(() => bodyRef.current?.querySelector("h2")?.focus());
  }
  function clear() {
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      /* sin almacenamiento */
    }
  }

  async function next(e) {
    e.preventDefault();
    const found = validateStep(step, form);
    if (Object.keys(found).length) {
      setErrors(found);
      requestAnimationFrame(() => bodyRef.current?.querySelector('[aria-invalid="true"], .field-error')?.scrollIntoView({ block: "center" }));
      return;
    }
    if (step < REQUEST_STEPS.length - 1) return goTo(step + 1);
    if (lock.current) return; // sin reenvíos duplicados
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await onCreate(toPayload(form, user), draft.key);
      clear();
    } catch (err) {
      setError(friendlyError(err));
      lock.current = false;
      setBusy(false);
    }
  }

  const dirty = step > 0 || form.picks.length > 0 || form.detail.trim() !== "";

  return (
    <Card className="wizard enter" aria-labelledby="wizard-title">
      <div className="wizard-head">
        <div>
          <p className="eyebrow">Nueva solicitud</p>
          <h1 id="wizard-title" className="wizard-title">Solicitar recogida</h1>
        </div>
        <Button variant="ghost" icon={X} disabled={busy} onClick={() => (dirty ? setConfirmCancel(true) : onCancel())}>
          Cancelar
        </Button>
      </div>
      <Stepper steps={REQUEST_STEPS} current={step} onStep={busy ? undefined : goTo} label="Pasos de la solicitud" />

      <form className="form-stack" onSubmit={next} noValidate ref={bodyRef}>
        <fieldset className="plain form-stack" disabled={busy}>
          <h2 tabIndex={-1} className="step-title">
            {["¿Qué deseas entregar?", "Información de recogida", "Confirmar solicitud"][step]}
          </h2>
          <div className="step-body" key={step}>
            {step === 0 && <WasteStep form={form} update={update} errors={errors} />}
            {step === 1 && <PlaceTimeStep form={form} update={update} errors={errors} user={user} />}
            {step === 2 && <ReviewStep payload={toPayload(form, user)} residuo={form.residuo} goTo={goTo} />}
          </div>
        </fieldset>
        {Object.keys(errors).length > 0 && (
          <Alert tone="error">Revisa los campos marcados antes de continuar.</Alert>
        )}
        {error && <Alert tone="error" title="No se pudo enviar la solicitud">{error} Tus datos siguen aquí; puedes intentarlo de nuevo.</Alert>}
        <div className="btn-group wizard-actions">
          {step > 0 && (
            <Button variant="secondary" size="lg" icon={ArrowLeft} disabled={busy} onClick={() => goTo(step - 1)}>
              Atrás
            </Button>
          )}
          <Button type="submit" size="lg" loading={busy} icon={step === 2 ? Send : undefined} iconEnd={step < 2 ? ArrowRight : undefined}>
            {step < 2 ? "Continuar" : busy ? "Enviando…" : "Confirmar solicitud"}
          </Button>
        </div>
      </form>

      <ConfirmDialog
        open={confirmCancel}
        tone="danger"
        title="¿Descartar esta solicitud?"
        confirmLabel="Sí, descartar"
        cancelLabel="Seguir editando"
        onCancel={() => setConfirmCancel(false)}
        onConfirm={() => {
          clear();
          setConfirmCancel(false);
          onCancel();
        }}
      >
        <p className="muted">Se borrarán los datos que has escrito. No se enviará nada.</p>
      </ConfirmDialog>
    </Card>
  );
}

export { RequestForm };
