import Brand from "../../components/Brand.jsx";

export function AuthLayout({ children, wide = false }) {
  return (
    <main id="contenido" className="auth">
      <header className="auth-identity"><Brand /></header>
      <div className="auth-panel" data-wide={wide || undefined}>
        {children}
      </div>
    </main>
  );
}
