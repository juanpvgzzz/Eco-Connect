import { cx } from "../../utils/cx.js";
import { Spinner } from "./Spinner.jsx";

// Botón del sistema: primary | secondary | danger | ghost.
// `loading` bloquea el doble envío y anuncia el estado ocupado.
export function Button({
  variant = "primary", size, block, loading = false, icon: Icon, iconEnd: IconEnd,
  className, type = "button", disabled, children, ...props
}) {
  return (
    <button
      type={type}
      className={cx("btn", `btn-${variant}`, size === "lg" && "btn-lg", block && "btn-block", className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <Spinner /> : Icon && <Icon size={20} aria-hidden="true" />}
      {children}
      {IconEnd && !loading && <IconEnd size={18} aria-hidden="true" />}
    </button>
  );
}
