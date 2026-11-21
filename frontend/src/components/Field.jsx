import { Children, cloneElement, isValidElement, useId } from "react";
import { CircleAlert } from "./icons.jsx";

// Etiqueta permanente + ayuda + error asociados al control mediante id/ARIA.
// El hijo único recibe id, aria-describedby y aria-invalid.
function Field({ label, hint, error, optional, children, className }) {
  const id = useId();
  const hintId = hint ? id + "-hint" : undefined;
  const errorId = error ? id + "-error" : undefined;
  const child = Children.only(children);
  const control = isValidElement(child)
    ? cloneElement(child, {
        id: child.props.id || id,
        "aria-describedby": [child.props["aria-describedby"], hintId, errorId].filter(Boolean).join(" ") || undefined,
        "aria-invalid": error ? true : undefined,
      })
    : child;
  return (
    <div className={["field", className].filter(Boolean).join(" ")}>
      <label className="field-label" htmlFor={child.props?.id || id}>
        {label}
        {optional && <span className="field-optional"> (opcional)</span>}
      </label>
      {control}
      {hint && <p className="field-hint" id={hintId}>{hint}</p>}
      {error && (
        <p className="field-error" id={errorId}>
          <CircleAlert size={16} aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}

export { Field };
