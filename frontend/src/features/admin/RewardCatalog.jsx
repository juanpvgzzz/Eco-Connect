import { useCallback, useEffect, useState } from "react";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { Field } from "../../components/Field.jsx";
import { Checkbox, NumberInput, Textarea, TextInput } from "../../components/ui/inputs.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";

const CATALOG = "/community/admin/rewards";
const EMPTY = { title: "", description: "", cost: "", stock: "0", active: false, validated: false };

export function RewardCatalog({ token }) {
  const [items, setItems] = useState(null);
  const [draft, setDraft] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const refresh = useCallback(async () => setItems(await request(CATALOG, { token })), [token]);
  useEffect(() => { refresh().catch((cause) => setError(friendlyError(cause))); }, [refresh]);

  function change(key, value) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      ...(["title", "description", "cost"].includes(key) && { validated: false }),
      [key]: value,
    }));
  }

  function edit({ id, ...settings }) {
    setEditing({ id, stock: settings.stock });
    setDraft(settings);
    setSaved(false);
    window.scrollTo({ top: 0 });
  }

  function clear() {
    setEditing(null);
    setDraft(EMPTY);
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const stock = Number(draft.stock);
      await request(editing ? `${CATALOG}/${editing.id}` : CATALOG, {
        method: editing ? "PUT" : "POST", token,
        body: { ...draft, cost: Number(draft.cost), stock: stock === editing?.stock ? undefined : stock },
      });
      clear();
      setSaved(true);
      await refresh();
    } catch (cause) { setError(friendlyError(cause)); }
    finally { setBusy(false); }
  }

  return <section className="stack" aria-labelledby="reward-catalog-title">
    <Card className="stack">
      <h2 id="reward-catalog-title">Recompensas del piloto</h2>
      <p className="muted">Cada recompensa y su costo en puntos son propuestas sujetas a validación de Fundación Santo Domingo.</p>
      <form className="content-editor" onSubmit={save}>
        <Field label="Nombre"><TextInput value={draft.title} onChange={(e) => change("title", e.target.value)} maxLength={120} required /></Field>
        <Field label="Descripción"><Textarea value={draft.description} onChange={(e) => change("description", e.target.value)} maxLength={1000} required /></Field>
        <Field label="Puntos requeridos"><NumberInput value={draft.cost} onChange={(e) => change("cost", e.target.value)} inputMode="numeric" min="1" max={Number.MAX_SAFE_INTEGER} step="1" required /></Field>
        <Field label="Unidades disponibles"><NumberInput value={draft.stock} onChange={(e) => change("stock", e.target.value)} inputMode="numeric" min="0" max="2147483647" step="1" required /></Field>
        <Checkbox label="La Fundación Santo Domingo validó la recompensa y su costo" checked={draft.validated} onChange={(e) => change("validated", e.target.checked)} />
        <Checkbox label="Habilitada para el piloto" checked={draft.active} onChange={(e) => change("active", e.target.checked)} />
        <div className="btn-group">
          <Button type="submit" size="lg" loading={busy}>{editing ? "Guardar cambios" : "Crear recompensa"}</Button>
          {editing && <Button variant="secondary" size="lg" onClick={clear} disabled={busy}>Cancelar edición</Button>}
        </div>
      </form>
      {saved && <Alert tone="success">Recompensa guardada.</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
    </Card>
    {items === null ? (!error && <Loading>Cargando recompensas…</Loading>) : items.length ? <div className="ops-grid">
      {items.map((item) => <Card as="article" className="stack" key={item.id}>
        <h3 className="wrap-anywhere">{item.title}</h3>
        <p className="wrap-anywhere">{item.description}</p>
        <p>{item.cost} puntos · {item.stock} disponibles</p>
        <p>{item.active ? "Habilitada" : "Deshabilitada"} · {item.validated ? "Validada" : "Pendiente de validación"}</p>
        <div><Button variant="secondary" size="lg" disabled={busy} onClick={() => edit(item)}>Editar</Button></div>
      </Card>)}
    </div> : <p>Aún no hay recompensas configuradas.</p>}
  </section>;
}
