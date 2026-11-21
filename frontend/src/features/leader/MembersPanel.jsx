import { useCallback, useEffect, useState } from "react";
import { UserPlus, Users } from "../../components/icons.jsx";
import { Field } from "../../components/Field.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { TextInput } from "../../components/ui/inputs.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";

// Integrantes del colectivo: registros operativos (sin cuenta de usuario).
// Solo los activos se pueden asignar a una recogida.
export function MembersPanel({ token, onChanged }) {
  const [members, setMembers] = useState(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(
    () => request("/recolecciones/recolectores?todos=true", { token }).then(setMembers).catch((e) => setError(friendlyError(e))),
    [token],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function act(key, fn) {
    setBusy(key);
    setError("");
    try {
      await fn();
      await load();
      onChanged?.();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy("");
    }
  }

  function add(e) {
    e.preventDefault();
    if (name.trim().length < 2) return setError("Escribe el nombre completo del integrante.");
    act("nuevo", async () => {
      await request("/recolecciones/recolectores", { token, body: { nombre: name } });
      setName("");
    });
  }

  return (
    <div className="members">
      <form className="members-form" onSubmit={add}>
        <Field label="Nombre del integrante" hint="Huerteros o recicladores de tu colectivo. No necesitan cuenta.">
          <TextInput value={name} maxLength={120} onChange={(e) => setName(e.target.value)} disabled={busy === "nuevo"} />
        </Field>
        <Button type="submit" size="lg" icon={UserPlus} loading={busy === "nuevo"}>Agregar integrante</Button>
      </form>
      {error && <Alert tone="error">{error}</Alert>}
      {members === null ? (
        <Loading>Cargando integrantes…</Loading>
      ) : !members.length ? (
        <EmptyState icon={Users} title="Aún no hay integrantes">
          Agrega a las personas de tu colectivo para poder asignarles recogidas.
        </EmptyState>
      ) : (
        <ul className="members-list">
          {members.map((m) => (
            <li key={m.id} className="member" data-active={m.active || undefined}>
              <div className="member-info">
                <span className="member-name">{m.full_name}</span>
                <span className="badge" data-tone={m.active ? "done" : "cancelled"}>{m.active ? "Activo" : "Inactivo"}</span>
              </div>
              <Button
                variant="secondary"
                size="lg"
                loading={busy === m.id}
                onClick={() => act(m.id, () => request(`/recolecciones/recolectores/${m.id}`, { token, method: "PATCH", body: { activo: !m.active } }))}
              >
                {m.active ? "Desactivar" : "Activar"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
