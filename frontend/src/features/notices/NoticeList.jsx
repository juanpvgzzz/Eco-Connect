import { BadgeCheck, Bell, CalendarClock, CalendarDays, CircleCheck, CircleX, Inbox, Phone, Search, Star, Ticket, Truck } from "../../components/icons.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { formatDate, formatWhen } from "../../utils/format.js";

const STYLE = {
  received: { icon: Inbox, tone: "pending" },
  reviewed: { icon: Search, tone: "review" },
  scheduled: { icon: CalendarDays, tone: "scheduled" },
  rescheduled: { icon: CalendarClock, tone: "scheduled" },
  failed: { icon: CircleX, tone: "warning" },
  cancelled: { icon: CircleX, tone: "cancelled" },
  collected: { icon: CircleCheck, tone: "done" },
  direct: { icon: Truck, tone: "done" },
  points: { icon: Star, tone: "points" },
  redeemed: { icon: Ticket, tone: "points" },
  workerNotice: { icon: Phone, tone: "review" },
  other: { icon: Bell, tone: "review" },
};

// Lista de avisos internos. `isNew` marca los no vistos en este dispositivo;
// `action(notice)` devuelve { label, onClick } para la acción contextual.
export function NoticeList({ notices, isNew = () => false, action, compact = false }) {
  if (!notices.length)
    return (
      <EmptyState icon={Bell} title="Sin avisos por ahora">
        Aquí verás cuando tus solicitudes cambien de estado.
      </EmptyState>
    );
  return (
    <ul className={compact ? "notice-list compact" : "notice-list"}>
      {notices.map((n) => {
        const { icon: Icon, tone } = STYLE[n.kind] || STYLE.other;
        const fresh = isNew(n);
        const act = action?.(n);
        const date = formatDate(n.date);
        const appointment = formatWhen(n.cita);
        return (
          <li key={n.id} className="notice" data-tone={tone} data-new={fresh || undefined}>
            <span className="notice-icon" aria-hidden="true"><Icon size={22} /></span>
            <div className="notice-body">
              <div className="notice-head">
                <h3>{n.title}</h3>
                {fresh ? (
                  <span className="badge" data-tone="new"><BadgeCheck size={14} aria-hidden="true" />Nuevo</span>
                ) : (
                  date && <span className="visually-hidden">Visto</span>
                )}
                {n.points > 0 && <span className="badge data" data-tone="points">+{n.points} pts</span>}
              </div>
              {n.text && <p>{n.text}</p>}
              {appointment && <p className="notice-when"><CalendarDays size={16} aria-hidden="true" /> {appointment}</p>}
              {n.reason && <p className="muted">Motivo: {n.reason}</p>}
              <div className="notice-foot">
                {date && <time className="muted data" dateTime={n.date}>{date}</time>}
                {act && <Button variant="ghost" className="notice-action" onClick={act.onClick}>{act.label}</Button>}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
