import { CalendarDays, Check, CircleX, Clock3, Search } from "./icons.jsx";
import { nameOf, stageOf } from "../utils/format.js";

const ICONS = { pending: Clock3, review: Search, scheduled: CalendarDays, done: Check, cancelled: CircleX };

// Insignia de estado: siempre icono + texto, nunca solo color.
function CollectionStatus({ value }) {
  const stage = stageOf[value] || "pending";
  const Icon = ICONS[stage];
  return (
    <span className="badge" data-tone={stage}>
      <Icon size={14} aria-hidden="true" />
      {nameOf[value] || value}
    </span>
  );
}

export { CollectionStatus, CollectionStatus as StatusBadge };
