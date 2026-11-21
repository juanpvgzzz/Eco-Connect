import { Component } from "react";
import { RotateCcw, TriangleAlert } from "./icons.jsx";

// Evita la pantalla en blanco: si un componente falla al renderizar,
// muestra un mensaje y permite reintentar sin perder la sesión.
export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Error de interfaz:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="page" style={{ paddingBlock: "2rem" }}>
        <section className="card stack" role="alert" style={{ maxWidth: "32rem", marginInline: "auto" }}>
          <span className="dialog-icon" style={{ background: "var(--eco-danger-50)", color: "var(--eco-danger)" }} aria-hidden="true">
            <TriangleAlert size={24} />
          </span>
          <h2>Algo no salió como esperábamos</h2>
          <p className="muted">
            {this.props.message || "Esta sección no se pudo mostrar. Tus datos están a salvo; puedes intentarlo de nuevo."}
          </p>
          <div className="btn-group">
            <button type="button" className="btn btn-primary btn-lg" onClick={() => this.setState({ error: null })}>
              <RotateCcw size={20} aria-hidden="true" /> Reintentar
            </button>
            <button type="button" className="btn btn-secondary btn-lg" onClick={() => window.location.reload()}>
              Recargar página
            </button>
          </div>
        </section>
      </div>
    );
  }
}
