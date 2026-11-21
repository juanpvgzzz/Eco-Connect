import { useEffect, useRef, useState } from "react";
import { Bell, LogOut, Menu, X } from "../../components/icons.jsx";
import Brand from "../../components/Brand.jsx";
import { isDemo } from "../../services/api.js";

export function AppHeader({ user, unread = 0, view, onNotices, onLogout, busy, menu = [], residentHome = false }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const panel = useRef(null);

  const close = (restoreFocus = true) => {
    setOpen(false);
    if (restoreFocus) requestAnimationFrame(() => button.current?.focus());
  };

  useEffect(() => {
    if (!open) return;
    const dialog = panel.current;
    dialog?.showModal();
    dialog?.querySelector("button")?.focus();
    document.body.classList.add("drawer-open");
    return () => {
      if (dialog?.open) dialog.close();
      document.body.classList.remove("drawer-open");
    };
  }, [open]);

  // Cerrar el menú si la vista cambia por cualquier otra vía.
  useEffect(() => setOpen(false), [view]);

  const choose = (fn) => () => {
    close(false);
    fn();
    requestAnimationFrame(() => document.getElementById("contenido")?.focus({ preventScroll: true }));
  };

  return (
    <header className="app-header" data-resident-home={residentHome || undefined}>
      <a href="#contenido" className="skip-link">Saltar al contenido</a>
      <div className="page app-header-inner">
        <Brand />
        <div className="header-actions">
          {isDemo && <span className="badge" data-tone="new">Demo</span>}
          {onNotices && (
            <button
              type="button"
              className="header-btn"
              onClick={onNotices}
              aria-current={view === "avisos" ? "page" : undefined}
              aria-label={residentHome ? "Notificaciones" : unread ? `Avisos, ${unread} nuevos` : "Avisos"}
              aria-description={residentHome && unread ? `${unread} ${unread === 1 ? "nueva" : "nuevas"}` : undefined}
            >
              <Bell size={22} />
              {unread > 0 && <span className={residentHome ? "home-notice-dot" : "count"} aria-hidden="true">{residentHome ? null : unread > 9 ? "9+" : unread}</span>}
            </button>
          )}
          <button
            ref={button}
            type="button"
            className="header-btn"
            aria-expanded={open}
            aria-controls={open ? "menu-lateral" : undefined}
            aria-label="Abrir menú"
            onClick={() => setOpen(true)}
          >
            <Menu size={residentHome ? 22 : 24} />
            <span className="menu-label">Menú</span>
          </button>
        </div>
      </div>

      {open && (
        <dialog
          id="menu-lateral"
          ref={panel}
          className="drawer-layer"
          aria-label="Menú"
          onCancel={(event) => { event.preventDefault(); close(); }}
          onClick={(event) => { if (event.target === event.currentTarget) close(); }}
        >
          <nav className="drawer" aria-label="Secciones de EcoConecta">
            <div className="drawer-head">
              <div className="drawer-who">
                <span className="drawer-name">{user.profile.full_name}</span>
              </div>
              <button type="button" className="drawer-close" onClick={() => close()} aria-label="Cerrar menú">
                <X size={22} />
              </button>
            </div>
            <ul className="drawer-list">
              {menu.map(({ id, label, icon: Icon, onClick, current }) => (
                <li key={id}>
                  <button type="button" className="drawer-item" aria-current={current ? "page" : undefined} onClick={choose(onClick)}>
                    {Icon && <Icon size={22} />} {label}
                  </button>
                </li>
              ))}
              {onLogout && <li className="drawer-sep">
                <button type="button" className="drawer-item" disabled={busy} onClick={choose(onLogout)}>
                  <LogOut size={22} /> Cerrar sesión
                </button>
              </li>}
            </ul>
          </nav>
        </dialog>
      )}
    </header>
  );
}
