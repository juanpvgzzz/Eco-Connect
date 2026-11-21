import { Building2, Check, MapPinned, Pencil, RotateCcw, Signpost } from "../../components/icons.jsx";
import { Field } from "../../components/Field.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { ChoiceCard, Select, TextInput, Textarea } from "../../components/ui/inputs.jsx";
import { COMPLEMENT_TYPES, MAX_ADDRESS, STREET_TYPES, formatAddress } from "./address.js";

// Dirección colombiana: vial (Carrera 45 # 68-32) o por manzana (Manzana 12, Casa 8).
// Genera un texto canónico que el vecino puede revisar y editar antes de guardar.
export function AddressInput({ value, onChange, errors = {}, idPrefix = "address" }) {
  const set = (field) => (e) => onChange({ ...value, [field]: e.target.value });
  const preview = formatAddress(value);
  const editing = value.custom !== null && value.custom !== undefined;

  return (
    <div className="address">
      {!editing && (
        <>
          <fieldset className="plain">
            <legend className="field-label">¿Cómo se ubica tu vivienda?</legend>
            <div className="choice-grid compact">
              <ChoiceCard
                name={`${idPrefix}-mode`}
                value="block"
                checked={value.mode === "block"}
                onChange={() => onChange({ ...value, mode: "block" })}
                icon={Building2}
                title="Manzana y casa"
                description="Ej.: Manzana 12, Casa 8"
                checkIcon={Check}
              />
              <ChoiceCard
                name={`${idPrefix}-mode`}
                value="street"
                checked={value.mode === "street"}
                onChange={() => onChange({ ...value, mode: "street" })}
                icon={Signpost}
                title="Calle o carrera"
                description="Ej.: Carrera 45 # 68-32"
                checkIcon={Check}
                tone="recycle"
              />
            </div>
          </fieldset>

          {value.mode === "street" ? (
            <div className="address-grid street enter" key="street">
              <Field label="Tipo de vía" className="area-type">
                <Select value={value.streetType} onChange={set("streetType")}>
                  {STREET_TYPES.map((t) => <option key={t}>{t}</option>)}
                </Select>
              </Field>
              <Field label="Número" error={errors.number} className="area-number">
                <TextInput value={value.number} onChange={set("number")} inputMode="text" maxLength={15} placeholder="45" autoComplete="off" />
              </Field>
              <Field label="Letra o sufijo" optional className="area-letter">
                <TextInput value={value.letter} onChange={set("letter")} maxLength={10} placeholder="A, Bis, Sur" autoComplete="off" />
              </Field>
              <Field label="# Vía secundaria" error={errors.cross} className="area-cross">
                <TextInput value={value.cross} onChange={set("cross")} maxLength={15} placeholder="68" autoComplete="off" />
              </Field>
              <Field label="Sufijo" optional className="area-crossSuffix">
                <TextInput value={value.crossSuffix} onChange={set("crossSuffix")} maxLength={10} placeholder="B" autoComplete="off" />
              </Field>
              <Field label="Placa" error={errors.plate} className="area-plate">
                <TextInput value={value.plate} onChange={set("plate")} maxLength={15} placeholder="32" autoComplete="off" />
              </Field>
              <Field label="Complemento" optional className="area-ctype">
                <Select value={value.complementType} onChange={set("complementType")}>
                  {COMPLEMENT_TYPES.map((t) => <option key={t}>{t}</option>)}
                </Select>
              </Field>
              <Field label="Número del complemento" optional className="area-cvalue">
                <TextInput value={value.complement} onChange={set("complement")} maxLength={20} placeholder="301" autoComplete="off" />
              </Field>
            </div>
          ) : (
            <div className="address-grid block enter" key="block">
              <Field label="Manzana" error={errors.manzana}>
                <TextInput value={value.manzana} onChange={set("manzana")} maxLength={15} placeholder="12" autoComplete="off" />
              </Field>
              <Field label="Casa o lote" error={errors.casa}>
                <TextInput value={value.casa} onChange={set("casa")} maxLength={15} placeholder="08" autoComplete="off" />
              </Field>
              <Field label="Bloque o torre" optional>
                <TextInput value={value.bloque} onChange={set("bloque")} maxLength={15} autoComplete="off" />
              </Field>
              <Field label="Apartamento" optional>
                <TextInput value={value.apto} onChange={set("apto")} maxLength={15} autoComplete="off" />
              </Field>
              <Field label="Conjunto o sector" optional className="span-2">
                <TextInput value={value.conjunto} onChange={set("conjunto")} maxLength={60} placeholder="Ej.: Conjunto Los Almendros" autoComplete="off" />
              </Field>
            </div>
          )}

          <div className="form-grid two">
            <Field label="Barrio o sector" error={errors.sector}>
              <TextInput value={value.sector} onChange={set("sector")} maxLength={60} autoComplete="address-level3" />
            </Field>
            <Field label="Referencias para llegar" optional error={errors.references}>
              <TextInput value={value.references} onChange={set("references")} maxLength={80} placeholder="Ej.: frente al parque" autoComplete="off" />
            </Field>
          </div>
        </>
      )}

      <div className="address-preview" aria-live="polite">
        <div className="address-preview-head">
          <MapPinned size={20} aria-hidden="true" />
          <span className="field-label">{editing ? "Edita tu dirección" : "Así quedará tu dirección"}</span>
        </div>
        {editing ? (
          <Field label="Dirección completa" error={errors.custom} hint={`${value.custom.length}/${MAX_ADDRESS} caracteres`}>
            <Textarea value={value.custom} onChange={set("custom")} maxLength={MAX_ADDRESS} rows={3} />
          </Field>
        ) : (
          <p className="address-preview-text">{preview}</p>
        )}
        <div>
          {editing ? (
            <Button variant="ghost" icon={RotateCcw} onClick={() => onChange({ ...value, custom: null })}>
              Volver a los campos
            </Button>
          ) : (
            <Button variant="ghost" icon={Pencil} onClick={() => onChange({ ...value, custom: preview })}>
              Editar el texto
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
