import { useCallback, useEffect, useState } from "react";
import { request } from "../services/api.js";
import { friendlyError } from "../services/errors.js";
import { Login } from "../features/auth/Login.jsx";
import { Dashboard } from "../features/operations/Dashboard.jsx";
import { AdminDashboard } from "../features/admin/AdminDashboard.jsx";
import { EducationLibrary } from "../features/resident/EducationLibrary.jsx";
import { Alert } from "../components/ui/Alert.jsx";
import { Loading } from "../components/ui/Spinner.jsx";
import { sessionKey } from "../utils/format.js";

export async function restoreSession(token) {
  const user = await request("/accounts/me", { token });
  const role = user.profile.role;
  if (!["leader", "resident", "business", "admin", "field_worker"].includes(role))
    throw Error("Este perfil no tiene acceso al panel.");
  if (role === "field_worker" && (!user.worker_id || !["huerta", "reciclaje"].includes(user.collective_flow)))
    throw Error("La cuenta de recolector debe estar vinculada a un integrante activo de su colectivo.");
  if (role === "leader" && (!user.collective_id || !["huerta", "reciclaje"].includes(user.collective_flow)))
    throw Error("La cuenta de coordinación necesita un colectivo autorizado.");
  sessionStorage.setItem(sessionKey, token);
  return { token, user };
}

// El token se guarda en sessionStorage (comportamiento existente); el PIN nunca.
function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initError, setInitError] = useState("");
  const [guide, setGuide] = useState(false); // guía ambiental pública (sin sesión)

  const end = useCallback(() => {
    sessionStorage.removeItem(sessionKey);
    setSession(null);
  }, []);

  async function restore(token) {
    setSession(await restoreSession(token));
  }

  useEffect(() => {
    const token = sessionStorage.getItem(sessionKey);
    if (!token) {
      setLoading(false);
      return;
    }
    restore(token)
      .catch((e) => {
        end();
        setInitError(friendlyError(e));
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading)
    return (
      <main id="contenido" className="app-main">
        <Loading>Cargando tu sesión…</Loading>
      </main>
    );
  if (session?.user.profile.role === "admin") return <AdminDashboard {...session} end={end} />;
  if (session) return <Dashboard {...session} end={end} />;
  if (guide)
    return (
      <main id="contenido" className="app-main">
        <EducationLibrary onBack={() => setGuide(false)} backLabel="Volver a iniciar sesión" />
      </main>
    );
  return (
    <>
      {initError && (
        <div className="page" style={{ paddingTop: "1rem" }}>
          <Alert tone="warning" onClose={() => setInitError("")}>{initError}</Alert>
        </div>
      )}
      <Login
        onGuide={() => setGuide(true)}
        onLogin={async (body) => {
          setInitError("");
          const login = await request("/accounts/login", { body });
          await restore(login.access_token);
        }}
      />
    </>
  );
}

export { App };
