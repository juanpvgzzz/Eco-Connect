import { useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Store, UserPlus, House } from "../../components/icons.jsx";
import { request, isDemo } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { Field } from "../../components/Field.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Stepper } from "../../components/ui/Stepper.jsx";
import { PhoneInput, PinInput, TextInput } from "../../components/ui/inputs.jsx";
import { AddressInput } from "../address/AddressInput.jsx";
import { emptyAddress, formatAddress, validateAddress } from "../address/address.js";
import {
  collapseSpaces, formatPhone, normalizeNationalId, normalizePhone,
  validateMobile, validateName, validateNationalId, validatePin,
} from "./validation.js";

const STEPS = ["Datos y contacto", "Dirección", "Seguridad"];

// Registro en tres pasos cortos. Los datos se conservan al ir y volver;
// el PIN vive solo en memoria y nunca se guarda en el navegador.
function Registration({ onBack, onCreated }) {
  const [step, setStep] = useState(0);
  const [person, setPerson] = useState({ full_name: "", national_id: "", phone: "", kind: "household" });
  const [address, setAddress] = useState(emptyAddress);
  const [pin, setPin] = useState({ pin: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const formRef = useRef(null);

  const setField = (setter, field) => (e) => {
    setter((v) => ({ ...v, [field]: e.target.value }));
    if (errors[field]) setErrors((v) => ({ ...v, [field]: "" }));
  };

  function focusFirstError() {
    requestAnimationFrame(() => formRef.current?.querySelector('[aria-invalid="true"]')?.focus());
  }

  function validate(index) {
    if (index === 0)
      return {
        full_name: validateName(person.full_name),
        national_id: validateNationalId(person.national_id),
        phone: validateMobile(person.phone),
      };
    if (index === 1) return validateAddress(address);
    const pinError = validatePin(pin.pin);
    return { pin: pinError, confirm: !pinError && pin.pin !== pin.confirm ? "Los dos PIN no coinciden." : "" };
  }

  function goTo(index) {
    setError("");
    setErrors({});
    setStep(index);
    requestAnimationFrame(() => formRef.current?.querySelector("h2")?.focus());
  }

  async function submit(e) {
    e.preventDefault();
    const found = validate(step);
    if (Object.values(found).some(Boolean)) {
      setErrors(found);
      focusFirstError();
      return;
    }
    if (step < STEPS.length - 1) return goTo(step + 1);
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    const body = {
      full_name: collapseSpaces(person.full_name),
      national_id: normalizeNationalId(person.national_id),
      phone: normalizePhone(person.phone),
      address: formatAddress(address),
      pin: pin.pin,
      kind: person.kind,
    };
    try {
      await request("/accounts", { body });
      onCreated(body.national_id);
    } catch (err) {
      if (err.status === 409) {
        setStep(0);
        setErrors({ national_id: "Ya existe una cuenta con esta cédula. Vuelve e inicia sesión." });
        focusFirstError();
      } else setError(friendlyError(err));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="auth-form enter">
      <header className="auth-heading">
        <h1>Crear cuenta</h1>
        <p className="muted">
          {isDemo ? "Usa datos ficticios para probar el registro." : "Tres pasos cortos y podrás solicitar tus recogidas."}
        </p>
      </header>
      <Stepper steps={STEPS} current={step} onStep={busy ? undefined : goTo} label="Pasos del registro" />
      <form ref={formRef} className="form-stack" onSubmit={submit} noValidate>
        <fieldset className="plain form-stack" disabled={busy} key={step}>
          <h2 tabIndex={-1} className="step-title enter">{STEPS[step]}</h2>
          {step === 0 && (
            <div className="form-stack enter">
              <h3 className="group-title">Datos personales</h3>
              <Field label="Tipo de cuenta">
                <div>
                  <div className="account-kind-options" role="group" aria-label="Tipo de cuenta">
                    <Button type="button" variant={person.kind === "household" ? "primary" : "secondary"} icon={House} onClick={() => setPerson((v) => ({ ...v, kind: "household" }))}>Hogar</Button>
                    <Button type="button" variant={person.kind === "business" ? "primary" : "secondary"} icon={Store} onClick={() => setPerson((v) => ({ ...v, kind: "business" }))}>Unidad productiva</Button>
                  </div>
                  <p className="muted">{person.kind === "business" ? "La cuenta de unidad productiva" : "La cuenta del hogar"} requiere habilitación del piloto por una persona administradora.</p>
                </div>
              </Field>
              <Field label="Nombre completo" error={errors.full_name} hint="Como aparece en tu documento.">
                <TextInput autoComplete="name" maxLength={160} value={person.full_name} onChange={setField(setPerson, "full_name")}
                  onBlur={() => setPerson((v) => ({ ...v, full_name: collapseSpaces(v.full_name) }))} />
              </Field>
              <Field label="Cédula" error={errors.national_id} hint="Solo números. Puedes escribirla con o sin puntos.">
                <TextInput className="data" inputMode="numeric" autoComplete="username" maxLength={32}
                  value={person.national_id} onChange={setField(setPerson, "national_id")} />
              </Field>
              <h3 className="group-title">Contacto</h3>
              <Field label="Celular" error={errors.phone} hint="10 dígitos, empieza por 3. Ejemplo: 300 123 4567.">
                <PhoneInput maxLength={16} value={person.phone} onChange={setField(setPerson, "phone")}
                  onBlur={() => !validateMobile(person.phone) && setPerson((v) => ({ ...v, phone: formatPhone(normalizePhone(v.phone)) }))} />
              </Field>
            </div>
          )}
          {step === 1 && (
            <div className="enter">
              <AddressInput idPrefix="registro" value={address} errors={errors} onChange={(next) => { setAddress(next); setErrors({}); }} />
            </div>
          )}
          {step === 2 && (
            <div className="form-stack enter">
              <Field label="Crea tu PIN" error={errors.pin} hint="Entre 4 y 12 números. Lo usarás para entrar.">
                <PinInput autoComplete="new-password" maxLength={12} value={pin.pin} onChange={setField(setPin, "pin")} />
              </Field>
              <Field label="Repite el PIN" error={errors.confirm}>
                <PinInput autoComplete="new-password" maxLength={12} value={pin.confirm} onChange={setField(setPin, "confirm")} />
              </Field>
              <dl className="summary">
                <div className="summary-row"><dt>Nombre</dt><dd>{collapseSpaces(person.full_name)}</dd>
                  <Button variant="ghost" onClick={() => goTo(0)}>Cambiar</Button></div>
                <div className="summary-row"><dt>Cédula</dt><dd className="data">{normalizeNationalId(person.national_id)}</dd></div>
                <div className="summary-row"><dt>Celular</dt><dd className="data">{formatPhone(normalizePhone(person.phone))}</dd></div>
                <div className="summary-row"><dt>Dirección</dt><dd>{formatAddress(address)}</dd>
                  <Button variant="ghost" onClick={() => goTo(1)}>Cambiar</Button></div>
              </dl>
            </div>
          )}
        </fieldset>
        {error && <Alert tone="error">{error}</Alert>}
        <div className="btn-group">
          {step > 0 ? (
            <Button variant="secondary" size="lg" icon={ArrowLeft} disabled={busy} onClick={() => goTo(step - 1)}>Atrás</Button>
          ) : (
            <Button variant="secondary" size="lg" icon={ArrowLeft} disabled={busy} onClick={onBack}>Ya tengo cuenta</Button>
          )}
          <Button type="submit" size="lg" loading={busy} icon={step === 2 ? UserPlus : undefined} iconEnd={step < 2 ? ArrowRight : undefined}>
            {step < 2 ? "Continuar" : busy ? "Creando cuenta…" : "Crear cuenta"}
          </Button>
        </div>
      </form>
    </div>
  );
}

export { Registration };
export default Registration;
