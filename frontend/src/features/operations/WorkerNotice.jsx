import { useState } from "react";
import { Phone } from "../../components/icons.jsx";
import { Field } from "../../components/Field.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Select, TextInput } from "../../components/ui/inputs.jsx";
import { friendlyError } from "../../services/errors.js";

// Registra que la coordinadora avisó al recolector (POST /{id}/aviso-recolector).
// La aplicación no envía mensajes: solo deja constancia en el historial.
export function WorkerNotice({ row, perform }) {
  const [open, setOpen] = useState(false);
  const [canal, setCanal] = useState("llamada");
  const [nota, setNota] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (row.estado !== "programada" || !row.responsable) return null;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await perform(`/recolecciones/${row.id}/aviso-recolector`, { canal, ...(nota.trim() ? { nota } : {}) }, "Aviso al recolector registrado.");
      setOpen(false);
      setNota("");
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  if (!open)
    return (
      <Button variant="secondary" size="lg" icon={Phone} onClick={() => setOpen(true)}>
        Registrar aviso a {row.nombre_responsable || "el recolector"}
      </Button>
    );
  return (
    <form className="ops-form form-stack enter" onSubmit={submit}>
      <h4 className="ops-form-title">Registrar aviso al recolector</h4>
      <p className="muted">Anota cómo avisaste a {row.nombre_responsable || "la persona asignada"}. EcoConecta no envía el mensaje.</p>
      <fieldset className="plain form-grid two" disabled={busy}>
        <Field label="¿Cómo le avisaste?">
          <Select value={canal} onChange={(e) => setCanal(e.target.value)}>
            <option value="llamada">Llamada</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="mensaje">Mensaje de texto</option>
            <option value="en_persona">En persona</option>
          </Select>
        </Field>
        <Field label="Nota" optional>
          <TextInput maxLength={300} value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Ej.: confirmó la hora" />
        </Field>
      </fieldset>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="btn-group">
        <Button variant="secondary" size="lg" disabled={busy} onClick={() => setOpen(false)}>Volver</Button>
        <Button type="submit" size="lg" loading={busy}>Registrar aviso</Button>
      </div>
    </form>
  );
}
