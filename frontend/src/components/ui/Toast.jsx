import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { CircleAlert, CircleCheck, X } from "../icons.jsx";

const ToastContext = createContext({ show: () => {} });

// Notificaciones temporales con React + CSS nativo. La región aria-live
// existe siempre para que los lectores de pantalla anuncien cada mensaje.
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const seq = useRef(0);
  const dismiss = useCallback((id) => setItems((list) => list.filter((t) => t.id !== id)), []);
  const show = useCallback((message, { tone = "success", duration = 5000 } = {}) => {
    const id = ++seq.current;
    setItems((list) => [...list.slice(-2), { id, message, tone }]);
    setTimeout(() => dismiss(id), duration);
  }, [dismiss]);
  const value = useMemo(() => ({ show }), [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {items.map((t) => (
          <div className="toast" data-tone={t.tone} key={t.id}>
            {t.tone === "error" ? <CircleAlert size={20} aria-hidden="true" /> : <CircleCheck size={20} aria-hidden="true" />}
            <span>{t.message}</span>
            <button type="button" className="btn btn-ghost btn-icon" onClick={() => dismiss(t.id)} aria-label="Cerrar notificación">
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
