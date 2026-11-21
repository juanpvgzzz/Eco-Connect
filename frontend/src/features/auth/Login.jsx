import { useRef, useState } from "react";
import { ArrowRight, BookOpen, CircleUserRound, Recycle, Sprout, UserPlus } from "../../components/icons.jsx";
import { isDemo } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { demoProfiles } from "../../demo.js";
import { Field } from "../../components/Field.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { PinInput, TextInput } from "../../components/ui/inputs.jsx";
import { AuthLayout } from "./AuthLayout.jsx";
import { Registration } from "./Registration.jsx";
import { normalizeNationalId, validateNationalId } from "./validation.js";

function Login({ onLogin, onGuide }) {
  const [registering, setRegistering] = useState(false);
  const [success, setSuccess] = useState("");
  const [id, setId] = useState("");
  const [pin, setPin] = useState("");
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const idRef = useRef(null);
  const pinRef = useRef(null);

  async function login(nationalId, loginPin) {
    if (lock.current) return; // evita doble envío
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await onLogin({ national_id: nationalId, pin: loginPin });
    } catch (err) {
      setError(friendlyError(err));
      setPin("");
      pinRef.current?.focus();
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function submit(e) {
    e.preventDefault();
    const next = { id: validateNationalId(id), pin: pin ? "" : "Escribe tu PIN." };
    setErrors(next);
    if (next.id) return idRef.current?.focus();
    if (next.pin) return pinRef.current?.focus();
    login(normalizeNationalId(id), pin);
  }

  if (registering)
    return (
      <AuthLayout wide>
        <Registration
          onBack={() => setRegistering(false)}
          onCreated={(nationalId) => {
            setId(nationalId);
            setPin("");
            setErrors({});
            setSuccess("Tu cuenta está lista. Escribe tu PIN para entrar.");
            setRegistering(false);
          }}
        />
      </AuthLayout>
    );

  return (
    <AuthLayout>
      <div className="auth-form enter">
        <header className="auth-heading">
          <h1>Iniciar sesión</h1>
          <p className="muted">Usa tu cédula y tu PIN para entrar a EcoConecta.</p>
        </header>
        {success && <Alert tone="success" onClose={() => setSuccess("")}>{success}</Alert>}
        <form className="form-stack" onSubmit={submit} noValidate>
          <Field label="Cédula" error={errors.id} hint="Solo números, sin puntos.">
            <TextInput
              ref={idRef}
              name="national_id"
              autoComplete="username"
              inputMode="numeric"
              maxLength={32}
              className="data"
              value={id}
              disabled={busy}
              onChange={(e) => {
                setId(e.target.value);
                if (errors.id) setErrors((v) => ({ ...v, id: "" }));
              }}
            />
          </Field>
          <Field label="PIN" error={errors.pin}>
            <PinInput
              ref={pinRef}
              name="pin"
              autoComplete="current-password"
              maxLength={12}
              value={pin}
              disabled={busy}
              onChange={(e) => {
                setPin(e.target.value);
                if (errors.pin) setErrors((v) => ({ ...v, pin: "" }));
              }}
            />
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" size="lg" block loading={busy} iconEnd={ArrowRight}>
            {busy ? "Entrando…" : "Entrar"}
          </Button>
        </form>
        <div className="auth-secondary">
          <Button
            variant="secondary"
            size="lg"
            block
            icon={UserPlus}
            disabled={busy}
            onClick={() => {
              setError("");
              setSuccess("");
              setRegistering(true);
            }}
          >
            Crear cuenta
          </Button>
          {onGuide && (
            <Button variant="ghost" size="lg" block icon={BookOpen} onClick={onGuide}>
              Consultar la guía ambiental
            </Button>
          )}
        </div>
        {isDemo && (
          <section className="auth-demo" aria-labelledby="demo-title">
            <h2 id="demo-title">Acceso rápido de demostración</h2>
            <div className="chips">
              {demoProfiles.map((p, i) => {
                const Icon = [CircleUserRound, Sprout, Recycle][i];
                return (
                  <Button key={p.label} variant="ghost" icon={Icon} disabled={busy} onClick={() => login(p.national_id, p.pin)}>
                    {p.label}
                  </Button>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </AuthLayout>
  );
}

export { Login };
