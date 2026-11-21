import { useRef } from "react";

// Pestañas accesibles (tablist): flechas, Inicio y Fin mueven el foco.
// El panel lo renderiza quien las usa con id={`${id}-panel`}.
export function Tabs({ id, label, items, value, onChange }) {
  const refs = useRef([]);
  function onKeyDown(e, index) {
    const last = items.length - 1;
    const next = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    refs.current[next]?.focus();
    onChange(items[next].id);
  }
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item, index) => {
        const selected = item.id === value;
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            ref={(el) => (refs.current[index] = el)}
            type="button"
            role="tab"
            id={`${id}-tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`${id}-panel`}
            tabIndex={selected ? 0 : -1}
            className="tab"
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => onKeyDown(e, index)}
          >
            {Icon && <Icon size={18} aria-hidden="true" />}
            {item.label}
            {item.count !== undefined && <span className="tab-count data">{item.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
