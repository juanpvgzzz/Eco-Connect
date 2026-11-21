import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "../icons.jsx";
import { cx } from "../../utils/cx.js";

const ICONS = { error: CircleAlert, success: CircleCheck, info: Info, warning: TriangleAlert };

// Mensaje en línea. Error usa role="alert"; el resto, role="status".
export function Alert({ tone = "info", title, children, onClose, className }) {
  const Icon = ICONS[tone];
  return (
    <div className={cx("alert", `alert-${tone}`, className)} role={tone === "error" ? "alert" : "status"}>
      <Icon size={20} aria-hidden="true" />
      <div className="alert-body">
        {title && <p className="alert-title">{title}</p>}
        {children && <div>{children}</div>}
      </div>
      {onClose && (
        <button type="button" className="btn btn-ghost btn-icon alert-close" onClick={onClose} aria-label="Cerrar mensaje">
          <X size={18} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
