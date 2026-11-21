export function Spinner({ label }) {
  return <span className="spinner" role={label ? "status" : undefined} aria-label={label} aria-hidden={label ? undefined : "true"} />;
}

export function Loading({ children = "Cargando…" }) {
  return (
    <div className="loading" role="status">
      <Spinner />
      {children}
    </div>
  );
}
