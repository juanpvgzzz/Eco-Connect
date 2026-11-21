import { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { useToast } from "../../components/ui/Toast.jsx";
import { ErrorBoundary } from "../../components/ErrorBoundary.jsx";
import { byDateDesc, pointsNotice, residentNotice } from "../notices/model.js";
import { useSeen } from "../notices/useSeen.js";
import { ResidentHome } from "../resident/ResidentHome.jsx";
import { LeaderBoard } from "../leader/LeaderBoard.jsx";
import { AppHeader } from "./AppHeader.jsx";
import { CalendarDays, ClipboardList, UserRound, Users } from "../../components/icons.jsx";
import { WorkerHome } from "../worker/WorkerHome.jsx";

// Contenedor del panel: carga los datos reales según el rol y delega la
// presentación en ResidentHome (vecinos) o LeaderBoard (coordinadoras).
function Dashboard({ user, token, end }) {
  const leader = user.profile.role === "leader";
  const worker = user.profile.role === "field_worker";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("inicio");
  const [created, setCreated] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const seen = useSeen(user.id);
  const toast = useToast();

  const refresh = useCallback(async () => {
    const get = (path) => request(path, { token });
    if (leader) {
      const [rows, notices, workers, materials] = await Promise.all([
        get("/recolecciones"), get("/recolecciones/avisos"), get("/recolecciones/recolectores"), get("/recolecciones/materiales"),
      ]);
      setData({ rows, notices, workers, materials });
    } else if (worker) {
      // Recolector: únicamente sus asignaciones y el catálogo para registrar.
      const [rows, materials] = await Promise.all([get("/recolecciones/asignadas"), get("/recolecciones/materiales")]);
      setData({ rows, materials });
    } else {
      const [rows, notices, appointments, points, movements] = await Promise.all([
        get("/community/collections"),
        get("/community/notifications"),
        get("/community/appointments"),
        get("/community/points"),
        get("/community/points/movements").catch(() => []), // opcional: sin movimientos no hay avisos de puntos
      ]);
      setData({ rows, notices, appointments, points, movements });
    }
    setError("");
  }, [leader, token]);

  const report = useCallback((e) => (e.status === 401 ? end() : setError(friendlyError(e))), [end]);
  useEffect(() => {
    refresh().catch(report);
  }, [refresh, report]);

  // Crear solicitud: la Idempotency-Key llega del asistente y se reutiliza en reintentos.
  async function createRequest(payload, key) {
    try {
      const row = await request("/recolecciones", { token, body: payload, key });
      // Primero se recarga la lista para que la confirmación coincida con lo visible.
      await refresh().catch(report);
      setCreated(row.id);
      setView("inicio");
      window.scrollTo({ top: 0 });
    } catch (e) {
      if (e.status === 401) end();
      throw e;
    }
  }

  // Acciones operativas: lanza el error para mostrarlo junto a la tarjeta.
  async function perform(path, body, success) {
    try {
      await request(path, { token, body });
    } catch (e) {
      if (e.status === 401) end();
      throw e;
    }
    toast.show(success);
    await refresh().catch(report);
  }

  async function logout() {
    setLeaving(true);
    try {
      await request("/accounts/logout", { token, body: {} });
      end();
    } catch (e) {
      if (e.status === 401) end();
      else {
        setError(friendlyError(e));
        setLeaving(false);
      }
    }
  }

  const residentNotices = useMemo(
    () => (leader || worker || !data ? [] : [...data.notices.map(residentNotice), ...data.movements.map(pointsNotice)].sort(byDateDesc)),
    [leader, worker, data],
  );
  const unread = residentNotices.filter(seen.isNew).length;
  const resident = !leader && !worker;
  const go = (next) => {
    setView(next);
    window.scrollTo({ top: 0 });
  };

  const item = (id, label, icon) => ({ id, label, icon, current: view === id, onClick: () => go(id) });
  const menu = resident
    ? [item("perfil", "Mi perfil", UserRound)]
    : worker
      ? [item("inicio", "Mis recogidas", ClipboardList)]
      : [
          item("inicio", "Solicitudes", ClipboardList),
          item("calendario", "Calendario", CalendarDays),
          item("reportes", "Resumen por período", ClipboardList),
          item("integrantes", "Integrantes", Users),
        ];

  return (
    <>
      <AppHeader
        user={user}
        residentHome={resident && view === "inicio"}
        unread={unread}
        view={view}
        busy={leaving}
        onNotices={worker ? undefined : () => go("avisos")}
        onLogout={worker ? undefined : logout}
        menu={menu}
      />
      <main id="contenido" tabIndex={-1} className="app-main" data-role={leader ? "leader" : worker ? "worker" : "resident"}>
        {error && (
          <div className="page">
            <Alert tone="error" title="No se pudieron cargar los datos">
              {error}{" "}
              <Button variant="ghost" onClick={() => refresh().catch(report)}>Reintentar</Button>
            </Alert>
          </div>
        )}
        <ErrorBoundary>
          {worker ? (
            <WorkerHome user={user} data={data} perform={perform} token={token} logout={logout} busy={leaving} />
          ) : leader ? (
            <LeaderBoard flow={user.collective_flow} data={data} view={view} setView={setView} perform={perform} token={token} onMembersChanged={() => refresh().catch(report)} />
          ) : (
            <ResidentHome
              user={user}
              data={data}
              notices={residentNotices}
              view={view}
              setView={go}
              seen={seen}
              onCreate={createRequest}
              created={created}
              clearCreated={() => setCreated(null)}
              logout={logout}
              token={token}
            />
          )}
        </ErrorBoundary>
      </main>
    </>
  );
}

export { Dashboard };
