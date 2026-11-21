import { forwardRef, useState } from "react";
import { Eye, EyeOff } from "../icons.jsx";
import { cx } from "../../utils/cx.js";

// Controles nativos con los estilos del sistema. Se usan dentro de <Field>,
// que les inyecta id, aria-describedby y aria-invalid.

export const TextInput = forwardRef(function TextInput({ className, ...props }, ref) {
  return <input ref={ref} className={cx("input", className)} {...props} />;
});

export const NumberInput = forwardRef(function NumberInput({ className, ...props }, ref) {
  return <input ref={ref} type="number" inputMode="decimal" className={cx("input data", className)} {...props} />;
});

export function Select({ className, children, ...props }) {
  return <select className={cx("select", className)} {...props}>{children}</select>;
}

export function Textarea({ className, ...props }) {
  return <textarea className={cx("textarea", className)} {...props} />;
}

// Celular colombiano: prefijo visible +57 y teclado telefónico.
export const PhoneInput = forwardRef(function PhoneInput({ className, "aria-invalid": invalid, ...props }, ref) {
  return (
    <div className="input-group" data-invalid={invalid || undefined}>
      <span className="input-addon data" aria-hidden="true">+57</span>
      <input
        ref={ref}
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        className={cx("input data", className)}
        aria-invalid={invalid}
        {...props}
      />
    </div>
  );
});

// PIN numérico con control para mostrar u ocultar. Nunca se guarda en storage.
export const PinInput = forwardRef(function PinInput({ className, "aria-invalid": invalid, ...props }, ref) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="input-group" data-invalid={invalid || undefined}>
      <input
        ref={ref}
        type={visible ? "text" : "password"}
        inputMode="numeric"
        className={cx("input data", className)}
        aria-invalid={invalid}
        {...props}
      />
      <button
        type="button"
        className="input-toggle"
        aria-pressed={visible}
        aria-label={visible ? "Ocultar PIN" : "Mostrar PIN"}
        onClick={() => setVisible((v) => !v)}
      >
        {visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
        <span aria-hidden="true">{visible ? "Ocultar" : "Mostrar"}</span>
      </button>
    </div>
  );
});

export function Checkbox({ label, className, ...props }) {
  return (
    <label className={cx("check", className)}>
      <input type="checkbox" {...props} />
      <span>{label}</span>
    </label>
  );
}

export function Radio({ label, className, ...props }) {
  return (
    <label className={cx("check", className)}>
      <input type="radio" {...props} />
      <span>{label}</span>
    </label>
  );
}

// Opción compacta tipo píldora (checkbox o radio).
export function Chip({ label, icon: Icon, type = "checkbox", ...props }) {
  return (
    <label className="chip">
      <input type={type} {...props} />
      <span>
        {Icon && <Icon size={16} aria-hidden="true" className="chip-mark" />}
        {label}
      </span>
    </label>
  );
}

// Tarjeta grande de selección (radio): icono + título + descripción.
export function ChoiceCard({ icon: Icon, title, description, tone, checkIcon: CheckIcon, ...props }) {
  return (
    <label className="choice-card" data-tone={tone}>
      <input type="radio" {...props} />
      {Icon && <span className="choice-icon" aria-hidden="true"><Icon size={26} /></span>}
      <span className="grid gap-1">
        <span className="choice-title">{title}</span>
        {description && <span className="choice-text">{description}</span>}
      </span>
      <span className="choice-check" aria-hidden="true">{CheckIcon && <CheckIcon size={16} strokeWidth={3} />}</span>
    </label>
  );
}
