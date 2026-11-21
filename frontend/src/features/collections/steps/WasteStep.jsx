import { Check } from "../../../components/icons.jsx";
import { Field } from "../../../components/Field.jsx";
import { ChoiceCard, TextInput } from "../../../components/ui/inputs.jsx";
import { WASTE_TYPES } from "../materials.js";

// Paso 1: tipo de residuo (orgánico → huerteros, reciclable → recicladores)
// y material. El catálogo oficial no es visible para vecinos (la API lo
// restringe al colectivo), así que se ofrecen descripciones comunes y la
// coordinadora valida el material del catálogo al cerrar la recogida.
export function WasteStep({ form, update, errors }) {
  const type = WASTE_TYPES[form.residuo];
  const Icon = type.icon;
  const togglePick = (item) =>
    update({ picks: form.picks.includes(item) ? form.picks.filter((p) => p !== item) : [...form.picks, item] });

  return (
    <div className="form-stack">
      <p className="muted step-lead">Selecciona el tipo de residuo.</p>
      <fieldset className="plain">
        <legend className="visually-hidden">Tipo de residuo</legend>
        <div className="choice-grid">
          {Object.entries(WASTE_TYPES).map(([id, t]) => (
            <ChoiceCard
              key={id}
              name="residuo"
              value={id}
              checked={form.residuo === id}
              onChange={() => update({ residuo: id, picks: form.picks.filter((p) => t.examples.includes(p)) })}
              icon={t.icon}
              tone={t.tone}
              title={t.title}
              description={t.description}
              checkIcon={Check}
            />
          ))}
        </div>
      </fieldset>

      <fieldset className="plain" aria-describedby={errors.material ? "material-error" : undefined}>
        <legend className="field-label option-legend">
          Materiales <span className="field-optional">· elige uno o varios</span>
        </legend>
        <ul className="option-list">
          {type.examples.map((item) => {
            const checked = form.picks.includes(item);
            return (
              <li key={item}>
                <label className="option-row" data-tone={type.tone}>
                  <span className="option-icon" aria-hidden="true"><Icon size={20} /></span>
                  <span className="option-name">{item}</span>
                  <input type="checkbox" checked={checked} onChange={() => togglePick(item)} />
                  <span className="option-check" aria-hidden="true"><Check size={16} strokeWidth={3} /></span>
                </label>
              </li>
            );
          })}
        </ul>
      </fieldset>
      <Field
        label={form.picks.length ? "Detalles adicionales" : "Describe el material"}
        optional={form.picks.length > 0}
        hint="Ej.: dos bolsas medianas, cartón doblado."
        error={errors.material}
      >
        <TextInput id="material-detail" maxLength={300} value={form.detail} onChange={(e) => update({ detail: e.target.value })} />
      </Field>
    </div>
  );
}
