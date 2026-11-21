export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="empty">
      {Icon && <span className="empty-icon" aria-hidden="true"><Icon size={24} /></span>}
      <div className="empty-body">
        <h3>{title}</h3>
        {children && <p>{children}</p>}
        {action}
      </div>
    </div>
  );
}
