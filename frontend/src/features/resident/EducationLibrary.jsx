import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BookOpen } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { request } from "../../services/api.js";
import { AboutPartners } from "../../components/AboutPartners.jsx";
import { WASTE_TYPES } from "../collections/materials.js";

// Categorías gestionadas por administración (GET /content, público).
const SECTIONS = [
  ["separation", "Separación de residuos"],
  ["materials", "Materiales y buenas prácticas"],
  ["garden", "Huerta comunitaria"],
  ["routes", "Rutas", "Las rutas están pendientes de confirmación."],
  ["schedules", "Horarios", "Los horarios están pendientes de confirmación."],
];

// Guía ambiental pública. La orientación de flujo usa los mismos textos del
// formulario de solicitud; rutas y horarios solo aparecen si administración
// los publicó (no se inventa información territorial).
export function EducationLibrary({ onBack, backLabel = "Volver a Mi comunidad" }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    request("/content").then(setItems).catch((cause) => setError(cause.message || "No se pudo cargar el contenido."));
  }, []);
  const grouped = useMemo(() => SECTIONS.map(([id, label, pending]) => ({
    id, label, pending, entries: (items || []).filter((item) => item.category === id),
  })), [items]);

  return <section className="page view education-view" aria-labelledby="education-title">
    <Button variant="secondary" size="lg" icon={ArrowLeft} onClick={onBack}>{backLabel}</Button>
    <header className="section-title"><h1 id="education-title"><BookOpen size={26} /> Guía ambiental de EcoConecta</h1></header>

    <Card as="section" aria-labelledby="flow-guide-title" className="flow-guide">
      <h2 id="flow-guide-title">¿Orgánico o reciclable?</h2>
      <p className="muted">Elige el tipo de residuo al solicitar la recogida: así tu solicitud llega al colectivo que la atiende.</p>
      <div className="choice-grid">
        {Object.values(WASTE_TYPES).map((t) => {
          const Icon = t.icon;
          return <div key={t.title} className="flow-guide-item" data-tone={t.tone}>
            <span className="choice-icon" aria-hidden="true"><Icon size={24} /></span>
            <div>
              <h3>{t.title}</h3>
              <p>{t.description}</p>
              <p className="muted">Lo atiende: {t.team}. Ejemplos: {t.examples.join(", ").toLowerCase()}.</p>
            </div>
          </div>;
        })}
      </div>
    </Card>

    {error && <Alert tone="error" title="No se pudo cargar la guía">{error}</Alert>}
    {items === null && !error && <Loading>Cargando información publicada…</Loading>}
    {items && grouped.filter(({ entries, pending }) => entries.length || pending).map(({ id, label, pending, entries }) => (
      <section key={id} className="education-section" aria-labelledby={`edu-${id}`}>
        <h2 id={`edu-${id}`}>{label}</h2>
        {entries.length ? <div className="education-list">
          {entries.map((item) => <Card as="article" key={item.id} className="education-entry">
            <h3>{item.title}</h3>
            <p className="education-copy">{item.body}</p>
          </Card>)}
        </div> : <p>{pending}</p>}
      </section>
    ))}
    <AboutPartners />
  </section>;
}
