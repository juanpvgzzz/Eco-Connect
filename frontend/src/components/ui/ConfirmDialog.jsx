import { useEffect, useId, useRef } from "react";
import { CircleHelp, TriangleAlert } from "../icons.jsx";
import { Button } from "./Button.jsx";

// Confirmación con <dialog> nativo: foco atrapado, Escape cancela.
export function ConfirmDialog({ open, title, children, confirmLabel = "Confirmar", cancelLabel = "Volver", tone, busy, onConfirm, onCancel }) {
  const ref = useRef(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  const Icon = tone === "danger" ? TriangleAlert : CircleHelp;
  return (
    <dialog
      ref={ref}
      className="dialog"
      data-tone={tone}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onCancel();
      }}
    >
      {open && (
        <div className="dialog-body">
          <span className="dialog-icon" aria-hidden="true"><Icon size={24} /></span>
          <h2 id={titleId}>{title}</h2>
          {children}
          <div className="btn-group">
            <Button variant="secondary" size="lg" onClick={onCancel} disabled={busy} autoFocus>{cancelLabel}</Button>
            <Button variant={tone === "danger" ? "danger" : "primary"} size="lg" loading={busy} onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  );
}
