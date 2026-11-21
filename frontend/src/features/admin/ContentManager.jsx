import { useCallback, useEffect, useState } from "react";
import { BookOpen, Check, Edit3, Plus, Save } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { Field } from "../../components/Field.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { Select, TextInput } from "../../components/ui/inputs.jsx";
import { request } from "../../services/api.js";

const CATEGORIES = [
  ["materials", "Materiales admitidos"], ["separation", "Separación"],
  ["garden", "Huerta comunitaria"], ["routes", "Rutas"], ["schedules", "Horarios"],
];
const EMPTY = { title: "", category: "separation", body: "" };
const requiresConfirmation = (category) => category === "routes" || category === "schedules";
const CONFIRM_VALIDATED = "Confirma que la organización validó la información antes de publicarla.";

export function ContentManager({ token }) {
  const [items, setItems] = useState(null);
  const [draft, setDraft] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setItems(await request("/content/admin", { token }));
    setError("");
  }, [token]);
  useEffect(() => { refresh().catch((cause) => setError(cause.message)); }, [refresh]);

  function edit(item) {
    setEditing(item.id);
    setDraft({ title: item.title, category: item.category, body: item.body });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function save(event) {
    event.preventDefault();
    const published = items?.some((item) => item.id === editing && item.status === "published");
    if (published && requiresConfirmation(draft.category) && !window.confirm(CONFIRM_VALIDATED)) return;
    setBusy(true);
    setError("");
    try {
      await request(editing ? `/content/admin/${editing}` : "/content/admin", {
        token, method: editing ? "PUT" : "POST", body: draft,
      });
      setEditing(null);
      setDraft(EMPTY);
      await refresh();
    } catch (cause) { setError(cause.message || "No se pudo guardar el contenido."); }
    finally { setBusy(false); }
  }

  async function publish(item) {
    const prompt = `¿Publicar “${item.title}” para la comunidad?`;
    const message = requiresConfirmation(item.category) ? `${prompt}\n\n${CONFIRM_VALIDATED}` : prompt;
    if (!window.confirm(message)) return;
    setBusy(true);
    setError("");
    try {
      await request(`/content/admin/${item.id}/publish`, { token, method: "POST", body: {} });
      await refresh();
    } catch (cause) { setError(cause.message || "No se pudo publicar el contenido."); }
    finally { setBusy(false); }
  }

  return <section className="admin-content" aria-labelledby="content-title">
    <Card>
      <h2 id="content-title"><BookOpen size={22} /> Contenido ambiental</h2>
      <p className="muted">Publica solo instrucciones, rutas y horarios verificados por la organización.</p>
      <form className="content-editor" onSubmit={save}>
        <Field label="Título"><TextInput required maxLength={180} value={draft.title} onChange={(e) => setDraft((v) => ({ ...v, title: e.target.value }))} /></Field>
        <Field label="Categoría"><Select value={draft.category} onChange={(e) => setDraft((v) => ({ ...v, category: e.target.value }))}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></Field>
        <Field label="Información"><textarea required maxLength={20000} rows={8} className="input content-body" value={draft.body} onChange={(e) => setDraft((v) => ({ ...v, body: e.target.value }))} /></Field>
        {error && <Alert tone="error">{error}</Alert>}
        <div className="btn-group">
          <Button type="submit" size="lg" loading={busy} icon={editing ? Save : Plus}>{editing ? "Guardar cambios" : "Guardar borrador"}</Button>
          {editing && <Button type="button" variant="secondary" size="lg" disabled={busy} onClick={() => { setEditing(null); setDraft(EMPTY); }}>Cancelar edición</Button>}
        </div>
      </form>
    </Card>
    <h2>Artículos existentes</h2>
    {items === null ? <Loading>Cargando contenido publicado y borradores…</Loading> : items.length ? <div className="ops-grid">
      {items.map((item) => <Card as="article" key={item.id} className="content-item">
        <div className="admin-account-heading"><h3>{item.title}</h3><span className="badge" data-tone={item.status === "published" ? "success" : "muted"}>{item.status === "published" ? "Publicado" : "Borrador"}</span></div>
        <p className="muted">{CATEGORIES.find(([value]) => value === item.category)?.[1] || item.category}</p>
        <p className="content-preview">{item.body}</p>
        <div className="btn-group">
          <Button variant="secondary" size="lg" icon={Edit3} disabled={busy} onClick={() => edit(item)}>Editar</Button>
          {item.status !== "published" && <Button size="lg" icon={Check} loading={busy} onClick={() => publish(item)}>Publicar</Button>}
        </div>
      </Card>)}
    </div> : <Card><p>Aún no hay artículos ni horarios publicados.</p></Card>}
  </section>;
}
