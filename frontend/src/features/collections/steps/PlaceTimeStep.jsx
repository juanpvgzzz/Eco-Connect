import { Check, Home, MapPinPlus, Sun, Sunset } from "../../../components/icons.jsx";
import { Field } from "../../../components/Field.jsx";
import { Alert } from "../../../components/ui/Alert.jsx";
import { Chip, ChoiceCard, PhoneInput, Textarea, TextInput } from "../../../components/ui/inputs.jsx";
import { AddressInput } from "../../address/AddressInput.jsx";
import { DAYS, SLOTS } from "../availability.js";

const toggle = (list, id) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

// Paso 2: dirección (registrada u otra), contacto, disponibilidad y observaciones.
export function PlaceTimeStep({ form, update, errors, user }) {
  const allDays = form.days.length === DAYS.length;
  return (
    <div className="form-stack">
      <fieldset className="plain">
        <legend className="field-label">Dirección de recogida</legend>
        <div className="choice-grid">
          <ChoiceCard
            name="address-choice"
            checked={form.useOwnAddress}
            onChange={() => update({ useOwnAddress: true })}
            icon={Home}
            title="Mi dirección registrada"
            description={user.profile.address}
            checkIcon={Check}
          />
          <ChoiceCard
            name="address-choice"
            checked={!form.useOwnAddress}
            onChange={() => update({ useOwnAddress: false })}
            icon={MapPinPlus}
            tone="recycle"
            title="Otra dirección"
            description="Solo para esta solicitud."
            checkIcon={Check}
          />
        </div>
      </fieldset>
      {!form.useOwnAddress && (
        <div className="subpanel enter">
          <AddressInput idPrefix="solicitud" value={form.address} errors={errors} onChange={(address) => update({ address })} />
        </div>
      )}

      <Field label="Celular de contacto" error={errors.contact} hint="10 dígitos, empieza por 3.">
        <PhoneInput maxLength={16} value={form.contact} onChange={(e) => update({ contact: e.target.value })} />
      </Field>

      <fieldset className="plain" aria-describedby={errors.days ? "days-error" : undefined}>
        <legend className="field-label">¿Qué días puedes entregar el material?</legend>
        <div className="chips">
          {DAYS.map((d) => (
            <Chip key={d.id} label={d.label} icon={Check} checked={form.days.includes(d.id)}
              onChange={() => update({ days: toggle(form.days, d.id) })} />
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => update({ days: allDays ? [] : DAYS.map((d) => d.id) })}>
            {allDays ? "Quitar todos" : "Todos los días"}
          </button>
        </div>
        {errors.days && <p className="field-error" id="days-error">{errors.days}</p>}
      </fieldset>

      <fieldset className="plain" aria-describedby={errors.slots ? "slots-error" : undefined}>
        <legend className="field-label">¿En qué horario?</legend>
        <div className="choice-grid">
          {SLOTS.map((s) => (
            <label className="choice-card slot" key={s.id}>
              <input type="checkbox" checked={form.slots.includes(s.id)} onChange={() => update({ slots: toggle(form.slots, s.id) })} />
              <span className="choice-icon" aria-hidden="true">{s.id === "manana" ? <Sun size={24} /> : <Sunset size={24} />}</span>
              <span className="grid gap-1">
                <span className="choice-title">{s.label}</span>
                <span className="choice-text">{s.range}</span>
              </span>
              <span className="choice-check" aria-hidden="true"><Check size={16} strokeWidth={3} /></span>
            </label>
          ))}
        </div>
        {errors.slots && <p className="field-error" id="slots-error">{errors.slots}</p>}
      </fieldset>

      <Field label="Indicación sobre el horario" optional error={errors.note} hint="Ej.: después de las 9 a. m.; el sábado solo en la mañana.">
        <TextInput maxLength={150} value={form.note} onChange={(e) => update({ note: e.target.value })} />
      </Field>

      <Alert tone="info" title="Esto todavía no es una cita">
        Tu disponibilidad ayuda al colectivo a organizar la ruta. La recogida queda programada solo cuando el
        colectivo confirma el día, la hora y la persona responsable. Te avisaremos en “Avisos”.
      </Alert>

      <Field label="Observaciones" optional error={errors.observaciones} hint="Ej.: timbre dañado, llamar al llegar.">
        <Textarea maxLength={2000} rows={3} value={form.observaciones} onChange={(e) => update({ observaciones: e.target.value })} />
      </Field>
    </div>
  );
}
