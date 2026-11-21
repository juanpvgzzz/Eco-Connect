import { useCallback, useEffect, useState } from "react";
import { BookOpen, CalendarDays, ClipboardList, Search, ShieldCheck, Star, Ticket, UserCog, Users } from "../../components/icons.jsx";
import { AppHeader } from "../operations/AppHeader.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog.jsx";
import { Field } from "../../components/Field.jsx";
import { Select, TextInput, Checkbox } from "../../components/ui/inputs.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { ContentManager } from "./ContentManager.jsx";
import { PointRules } from "./PointRules.jsx";
import { Reports } from "./Reports.jsx";
import { RewardCatalog } from "./RewardCatalog.jsx";
import { AdminCalendar } from "../calendar/AdminCalendar.jsx";

const ADMIN_SECTIONS = [
  { id: "users", label: "Usuarios y roles", icon: Users },
  { id: "content", label: "Educación ambiental", icon: BookOpen },
  { id: "points", label: "Reglas de puntos", icon: Star },
  { id: "rewards", label: "Recompensas", icon: Ticket },
  { id: "reports", label: "Reportes", icon: ClipboardList },
  { id: "calendar", label: "Calendario y pendientes", icon: CalendarDays },
];

const ROLE_LABELS = {
  resident: "Vecino / hogar",
  business: "Unidad productiva",
  leader: "Coordinación",
  field_worker: "Recolector",
  admin: "Administrador",
};
const COLLECTIVE_LABELS = { huerta: "Huerteros · Orgánicos", reciclaje: "Recicladores · Reciclables" };

function roleChoices(account) {
  return [
    ...(account.kind === "household" ? ["resident"] : []),
    ...(account.kind === "business" ? ["business"] : []),
    "leader", "field_worker", "admin",
  ];
}

function AccountRow({ account, collectives, token, currentUser, onChanged }) {
  const [role, setRole] = useState(account.role);
  const [collective, setCollective] = useState(account.collective_id || "");
  const [pilotEnabled, setPilotEnabled] = useState(account.pilot_enabled);
  const [member, setMember] = useState(account.worker_id || "");
  const [members, setMembers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState(null);
  const needsCollective = role === "leader" || role === "field_worker";
  const needsMember = role === "field_worker";
  const dirty = role !== account.role || collective !== (account.collective_id || "") || pilotEnabled !== account.pilot_enabled
    || (needsMember && member !== (account.worker_id || ""));

  // Integrantes del colectivo elegido: la cuenta del recolector se vincula a uno existente.
  useEffect(() => {
    if (!needsMember || !collective) { setMembers([]); return; }
    request(`/accounts/admin/collectives/${collective}/members`, { token })
      .then(setMembers).catch((err) => setError(friendlyError(err)));
  }, [needsMember, collective, token]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      await request(`/accounts/admin/${account.id}/authorization`, {
        token,
        method: "PUT",
        body: {
          role, collective_id: needsCollective ? collective : null, pilot_enabled: (role === "business" || role === "resident") && pilotEnabled,
          ...(needsMember ? { worker_id: member } : {}),
        },
      });
      onChanged();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
      setConfirmation(null);
    }
  }

  async function toggleActive() {
    const next = !account.active;
    setBusy(true);
    setError("");
    try {
      await request(`/accounts/admin/${account.id}/active`, { token, method: "PATCH", body: { active: next } });
      onChanged();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
      setConfirmation(null);
    }
  }

  return (
    <Card as="article" className="admin-account">
      <div className="admin-account-heading">
        <div>
          <h3>{account.full_name}</h3>
          <p className="account-role">{ROLE_LABELS[account.role]}{account.collective_flow && ` · ${COLLECTIVE_LABELS[account.collective_flow] || ""}`}</p>
          <p className="muted">Cédula <span className="data">{account.national_id}</span></p>
        </div>
        <span className="badge" data-tone={account.active && (account.role !== "field_worker" || account.worker_id) ? "success" : "muted"}>
          {account.role === "field_worker" && !account.worker_id ? "Recolector sin vínculo" : account.active ? "Acceso activo" : "Acceso desactivado"}
        </span>
      </div>
      <div className="admin-account-form">
        <Field label="Perfil autorizado">
          <Select value={role} disabled={busy || !account.active || account.id === currentUser.id} onChange={(event) => setRole(event.target.value)}>
            {roleChoices(account).map((choice) => <option key={choice} value={choice}>{ROLE_LABELS[choice]}</option>)}
          </Select>
        </Field>
        {needsCollective && <Field label={needsMember ? "Colectivo del recolector" : "Colectivo de coordinación"}>
          <Select value={collective} disabled={busy || !account.active} onChange={(event) => setCollective(event.target.value)}>
            <option value="">Selecciona un colectivo</option>
            {collectives.map((item) => <option key={item.id} value={item.id}>{COLLECTIVE_LABELS[item.flow]}</option>)}
          </Select>
        </Field>}
        {needsMember && collective && <Field label="Integrante registrado" hint="Solo integrantes activos sin otra cuenta. La coordinadora los registra en «Integrantes».">
          <Select value={member} disabled={busy || !account.active} onChange={(event) => setMember(event.target.value)}>
            <option value="">Selecciona un integrante</option>
            {members.filter((m) => m.active && (!m.linked || m.account_id === account.id)).map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </Select>
        </Field>}
        {(role === "business" || role === "resident") && <Checkbox
          label={role === "business" ? "Habilitar esta unidad productiva para el piloto" : "Habilitar este hogar para el piloto"}
          checked={pilotEnabled}
          disabled={busy || !account.active}
          onChange={(event) => setPilotEnabled(event.target.checked)}
        />}
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="btn-group admin-account-actions">
        <Button size="lg" loading={busy} disabled={!dirty || !account.active || (needsCollective && !collective) || (needsMember && !member) || account.id === currentUser.id} icon={ShieldCheck} onClick={() => setConfirmation("authorization")}>
          Guardar autorización
        </Button>
        <Button size="lg" variant="secondary" loading={busy} disabled={account.id === currentUser.id} onClick={() => setConfirmation("active")}>
          {account.active ? "Desactivar acceso" : "Activar acceso"}
        </Button>
      </div>
      <ConfirmDialog
        open={Boolean(confirmation)}
        title={confirmation === "authorization" ? "¿Guardar la autorización?" : account.active ? "¿Desactivar el acceso?" : "¿Activar el acceso?"}
        confirmLabel={confirmation === "authorization" ? "Guardar autorización" : account.active ? "Desactivar acceso" : "Activar acceso"}
        tone={confirmation === "active" && account.active ? "danger" : undefined}
        busy={busy}
        onCancel={() => setConfirmation(null)}
        onConfirm={confirmation === "authorization" ? save : toggleActive}
      >
        <p>{account.full_name}{confirmation === "authorization" && ` pasará a tener el perfil «${ROLE_LABELS[role]}».`}</p>
      </ConfirmDialog>
    </Card>
  );
}

export function AdminDashboard({ user, token, end }) {
  const [accounts, setAccounts] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [collectives, setCollectives] = useState([]);
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [role, setRole] = useState("");
  const [section, setSection] = useState("users");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const params = new URLSearchParams();
    if (term.trim()) params.set("search", term.trim());
    if (role) params.set("role", role);
    params.set("limit", "50");
    params.set("offset", "0");
    const query = params.toString();
    const [rows, groups] = await Promise.all([
      request(`/accounts/admin/users${query ? `?${query}` : ""}`, { token }),
      request("/accounts/admin/collectives", { token }),
    ]);
    setAccounts(rows);
    setHasMore(rows.length === 50);
    setCollectives(groups);
    setError("");
  }, [role, term, token]);

  async function loadMore() {
    setBusy(true);
    try {
      const params = new URLSearchParams({ limit: "50", offset: String(accounts.length) });
      if (term.trim()) params.set("search", term.trim());
      if (role) params.set("role", role);
      const rows = await request(`/accounts/admin/users?${params}`, { token });
      setAccounts((current) => [...current, ...rows]);
      setHasMore(rows.length === 50);
    } catch (err) { setError(friendlyError(err)); }
    finally { setBusy(false); }
  }

  useEffect(() => { refresh().catch((err) => setError(friendlyError(err))); }, [refresh]);

  async function logout() {
    setBusy(true);
    try {
      await request("/accounts/logout", { token, body: {} });
      end();
    } catch (err) {
      if (err.status === 401) end();
      else setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  const menu = ADMIN_SECTIONS.map((item) => ({
    ...item, current: item.id === section,
    onClick: () => { setSection(item.id); window.scrollTo({ top: 0 }); },
  }));

  return <>
    <AppHeader user={user} view={section} menu={menu} onLogout={logout} busy={busy} />
    <main id="contenido" tabIndex={-1} className="app-main" data-role="admin">
      <div className="page view admin-view">
        <section className="ops-hero" aria-labelledby="admin-title">
          <span className="ops-hero-icon" aria-hidden="true"><UserCog size={30} /></span>
          <div><p>Gestión del piloto</p><h1 id="admin-title">Administración</h1></div>
        </section>
        <div className="admin-content-area">
        {section === "calendar" ? <AdminCalendar token={token} /> : section === "content" ? <ContentManager token={token} /> : section === "points" ? <PointRules token={token} /> : section === "rewards" ? <RewardCatalog token={token} /> : section === "reports" ? <Reports token={token} /> : <>
        <Card className="admin-directory">
          <div className="admin-directory-heading"><div><h2>Usuarios y roles</h2><p>Autoriza el acceso al piloto y vincula perfiles a su colectivo.</p></div>
            {accounts && <span className="data loaded-accounts">{accounts.length} cuentas visibles</span>}
          </div>
          <form className="admin-filters" onSubmit={(event) => { event.preventDefault(); setTerm(search); }}>
            <Field label="Buscar por nombre o cédula"><TextInput value={search} onChange={(event) => setSearch(event.target.value)} /></Field>
            <Field label="Filtrar por perfil"><Select value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="">Todos los perfiles</option>{Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Select></Field>
            <Button type="submit" size="lg" icon={Search}>Buscar</Button>
          </form>
        </Card>
        {accounts && !collectives.length && <Alert tone="warning">El piloto aún no tiene colectivos disponibles para autorizar coordinadoras.</Alert>}
        {error && <Alert tone="error" title="No se pudo completar la operación">{error}<Button variant="ghost" onClick={() => refresh().catch((err) => setError(friendlyError(err)))}>Reintentar</Button></Alert>}
        {!accounts ? <Loading>Cargando usuarios…</Loading> : accounts.length ? accounts.map((account) => <AccountRow
          key={account.id} account={account} collectives={collectives} token={token} currentUser={user}
          onChanged={() => { setBusy(true); refresh().catch((err) => setError(friendlyError(err))).finally(() => setBusy(false)); }}
        />) : <Card><p>No hay cuentas que coincidan con la búsqueda.</p></Card>}
        {hasMore && <Button size="lg" variant="secondary" loading={busy} onClick={loadMore}>Cargar otros 50 usuarios</Button>}
        </>}
        </div>
      </div>
    </main>
  </>;
}
