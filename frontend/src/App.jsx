import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  Bell,
  CalendarDays,
  Check,
  CircleUserRound,
  ClipboardList,
  Clock3,
  CircleX,
  CircleAlert,
  LogOut,
  MapPin,
  Plus,
  Recycle,
  RefreshCw,
  Sprout,
  Ticket,
} from "lucide-react";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/poppins/latin-600.css";
import "@fontsource/poppins/latin-700.css";
import { request, isDemo } from "./data";
import { demoProfiles } from "./demo";
import "./styles.css";

const nameOf = {
  received: "Recibida",
  under_review: "En revisión",
  scheduled: "Programada",
  collected: "Recolectada",
  cancelled: "Cancelada",
  recibida: "Recibida",
  revision: "En revisión",
  programada: "Programada",
  recolectada: "Recolectada",
  reprogramada: "Reprogramada",
  cancelada: "Cancelada",
};
const date = (value) =>
  new Intl.DateTimeFormat("es-CO", {
    timeZone: "America/Bogota",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
const formValues = (e) => Object.fromEntries(new FormData(e.currentTarget));
const sessionKey = isDemo ? "eco.demo.session" : "eco.api.session";
function Brand() {
  return (
    <span className="brand">
      <img
        src="/marca/ecoconecta.png"
        alt="EcoConecta Villas de San Pablo"
        width="2172"
        height="724"
      />
    </span>
  );
}
function CollectionStatus({ value }) {
  const label = nameOf[value] || value;
  const Icon =
    { Programada: CalendarDays, Recolectada: Check, Cancelada: CircleX }[
      label
    ] || Clock3;
  return (
    <span className="status">
      <Icon size={15} aria-hidden="true" />
      {label}
    </span>
  );
}
function Field({ label, children }) {
  return (
    <label className="field">
      {label}
      {children}
    </label>
  );
}

function Login({ onLogin }) {
  const [registering, setRegistering] = useState(false);
  const [success, setSuccess] = useState("");
  const [id, setId] = useState(""),
    [pin, setPin] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin({ national_id: id, pin });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login">
      <div className="loginCard">
        <section className="loginIdentity" aria-label="EcoConecta">
          <Brand />
          <div className="territory">
            <MapPin size={15} aria-hidden="true" /> Barranquilla
          </div>
        </section>
        <section className="loginPanel">
          <div className="loginInner">
            {registering ? (
              <Registration
                onBack={() => setRegistering(false)}
                onCreated={(nationalId) => {
                  setId(nationalId);
                  setPin("");
                  setSuccess(
                    "Cuenta creada. Ingresa tu PIN para iniciar sesión.",
                  );
                  setRegistering(false);
                }}
              />
            ) : (
              <>
                <h1>Iniciar sesión</h1>
                <p className="muted">Ingresa con tu cédula y PIN.</p>
                {success && <p role="status">{success}</p>}
                <form onSubmit={submit}>
                  <Field label="Cédula">
                    <input
                      autoComplete="username"
                      inputMode="numeric"
                      required
                      value={id}
                      onChange={(e) => setId(e.target.value)}
                    />
                  </Field>
                  <Field label="PIN">
                    <input
                      type="password"
                      autoComplete="current-password"
                      inputMode="numeric"
                      required
                      value={pin}
                      onChange={(e) => setPin(e.target.value)}
                    />
                  </Field>
                  {error && (
                    <p role="alert">
                      <CircleAlert size={18} aria-hidden="true" />
                      {error}
                    </p>
                  )}
                  <button className="primary w-full" disabled={busy}>
                    Entrar <ArrowRight size={18} />
                  </button>
                </form>
                <button
                  className="secondary registerLink"
                  disabled={busy}
                  onClick={() => {
                    setError("");
                    setSuccess("");
                    setRegistering(true);
                  }}
                >
                  Registrarse
                </button>
                {isDemo && (
                  <section className="demo">
                    <h3>Perfiles de demostración</h3>
                    <div className="profileChoices">
                      {demoProfiles.map((p, i) => {
                        const Icon = [CircleUserRound, Sprout, Recycle][i];
                        return (
                          <button
                            type="button"
                            className="chip"
                            aria-pressed={id === p.national_id && pin === p.pin}
                            key={p.label}
                            onClick={() => {
                              setId(p.national_id);
                              setPin(p.pin);
                            }}
                          >
                            <Icon size={16} />
                            {p.label}
                          </button>
                        );
                      })}
                    </div>
                  </section>
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function Registration({ onBack, onCreated }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const data = formValues(e);
    data.national_id = data.national_id.replace(/[.\s-]/g, "");
    if (!/^[0-9]{1,20}$/.test(data.national_id)) {
      setError("Revisa tu cédula. Debe tener entre 1 y 20 dígitos.");
      return;
    }
    for (const field of ["full_name", "address", "phone"])
      data[field] = data[field].trim();
    if (!data.full_name || !data.address || !data.phone) {
      setError("Completa el nombre, la dirección y el celular.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await request("/accounts", { body: data });
      onCreated(data.national_id);
    } catch (err) {
      setError(
        err.status === 409
          ? "Esta cédula ya tiene una cuenta. Vuelve a iniciar sesión."
          : err.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>Crear cuenta</h1>
      <p className="muted">
        {isDemo
          ? "Usa datos ficticios para probar el registro."
          : "Completa tus datos para solicitar recogidas."}
      </p>
      <form onSubmit={submit}>
        <fieldset disabled={busy} className="registrationGrid">
          <Field label="Nombre completo">
            <input
              name="full_name"
              autoComplete="name"
              maxLength={160}
              required
            />
          </Field>
          <Field label="Cédula">
            <input
              name="national_id"
              autoComplete="username"
              inputMode="numeric"
              maxLength={32}
              required
            />
          </Field>
          <Field label="Celular">
            <input
              name="phone"
              type="tel"
              autoComplete="tel"
              maxLength={32}
              required
            />
          </Field>
          <Field label="Dirección">
            <input
              name="address"
              autoComplete="street-address"
              maxLength={240}
              required
            />
          </Field>
          <Field label="Tipo de cuenta">
            <select name="kind" required defaultValue="">
              <option value="" disabled>
                Selecciona una opción
              </option>
              <option value="household">Hogar</option>
              <option value="business">Unidad productiva o negocio</option>
            </select>
          </Field>
          <Field label="PIN (4 a 12 dígitos)">
            <input
              type="password"
              name="pin"
              inputMode="numeric"
              autoComplete="new-password"
              pattern="[0-9]{4,12}"
              minLength={4}
              maxLength={12}
              required
            />
          </Field>
        </fieldset>
        {error && <p role="alert">{error}</p>}
        <button className="primary w-full" disabled={busy}>
          Crear cuenta
        </button>
      </form>
      <button
        className="secondary registerLink"
        onClick={onBack}
        disabled={busy}
      >
        Volver a iniciar sesión
      </button>
    </>
  );
}

function RequestForm({ user, onCreate, pending }) {
  const storageKey = sessionKey + ".request." + user.id;
  const [draft, setDraft] = useState(
    () =>
      JSON.parse(sessionStorage.getItem(storageKey) || "null") || {
        key: crypto.randomUUID(),
        data: {
          residuo: "organico",
          material: "",
          contacto: user.profile.phone,
          direccion: user.profile.address,
          generador:
            user.profile.kind === "business" ? "unidad_productiva" : "hogar",
          disponibilidad: "",
          observaciones: "",
        },
      },
  );
  function update(field, value) {
    const next = {
      key: crypto.randomUUID(),
      data: { ...draft.data, [field]: value },
    };
    sessionStorage.setItem(storageKey, JSON.stringify(next));
    setDraft(next);
  }
  function field(k) {
    return { value: draft.data[k], onChange: (e) => update(k, e.target.value) };
  }
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        sessionStorage.setItem(storageKey, JSON.stringify(draft));
        onCreate(draft, () => sessionStorage.removeItem(storageKey));
      }}
    >
      <h2>Nueva solicitud</h2>
      <fieldset disabled={pending}>
        <legend>Tipo de residuo</legend>
        <div className="flex gap-2 mb-4">
          {[
            ["organico", "Orgánico", Sprout],
            ["reciclable", "Reciclable", Recycle],
          ].map(([v, t, I]) => (
            <button
              type="button"
              key={v}
              aria-pressed={draft.data.residuo === v}
              className="choice"
              onClick={() => draft.data.residuo !== v && update("residuo", v)}
            >
              <I size={20} />
              {t}
            </button>
          ))}
        </div>
        <Field label="Material">
          <input
            required
            maxLength={500}
            placeholder="Ej. cáscaras de fruta"
            {...field("material")}
          />
        </Field>
        <Field label="Dirección de recogida">
          <input required maxLength={500} {...field("direccion")} />
        </Field>
        <Field label="Celular de contacto">
          <input required type="tel" maxLength={500} {...field("contacto")} />
        </Field>
        <Field label="Disponibilidad">
          <input
            required
            maxLength={500}
            placeholder="Ej. mañana entre 8 y 10 a. m."
            {...field("disponibilidad")}
          />
        </Field>
        <Field label="Observaciones (opcional)">
          <textarea maxLength={2000} {...field("observaciones")} />
        </Field>
        <button className="primary" disabled={pending}>
          Enviar solicitud <ArrowRight size={18} />
        </button>
      </fieldset>
    </form>
  );
}

function Actions({ row, run, pending }) {
  const [mode, setMode] = useState("");
  if (!["recibida", "revision", "programada"].includes(row.estado)) return null;
  const scheduled = row.estado === "programada";
  async function submit(e) {
    e.preventDefault();
    const values = formValues(e);
    if (mode === "programar") values.cita += ":00-05:00";
    if (await run("/recolecciones/" + row.id + "/" + mode, values)) setMode("");
  }
  return (
    <div className="actions">
      <div className="flex flex-wrap gap-2">
        <button className="secondary" onClick={() => setMode("programar")}>
          <CalendarDays size={17} />
          {scheduled ? "Reprogramar" : "Agendar visita"}
        </button>
        {scheduled && (
          <button className="primary" onClick={() => setMode("cerrar")}>
            <Check size={17} />
            Cerrar recogida
          </button>
        )}
      </div>
      {mode && (
        <form key={mode} onSubmit={submit} className="mt-4">
          <fieldset disabled={pending}>
            {mode === "programar" ? (
              <>
                <Field label="Fecha y hora en Barranquilla">
                  <input type="datetime-local" name="cita" required />
                </Field>
                {scheduled && (
                  <Field label="Motivo del cambio">
                    <input name="motivo" required maxLength={500} />
                  </Field>
                )}
              </>
            ) : (
              <>
                <Field label="Material recogido">
                  <input
                    name="material"
                    defaultValue={row.solicitud?.material}
                    maxLength={500}
                    required
                  />
                </Field>
                <Field label="Kilos aceptados">
                  <input
                    name="kilos"
                    type="number"
                    min=".001"
                    max="10000"
                    step=".001"
                    required
                  />
                </Field>
                <Field label="Resultado">
                  <select name="resultado">
                    <option value="total">Total</option>
                    <option value="parcial">Parcial</option>
                  </select>
                </Field>
              </>
            )}
            <button className="primary">
              Confirmar {mode === "cerrar" ? "cierre" : "cita"}
            </button>{" "}
            <button type="button" onClick={() => setMode("")}>
              Volver
            </button>
          </fieldset>
        </form>
      )}
    </div>
  );
}

function Dashboard({ user, token, end }) {
  const leader = user.profile.role === "leader",
    [tab, setTab] = useState("panel"),
    [data, setData] = useState(null);
  const [error, setError] = useState(""),
    [feedback, setFeedback] = useState(""),
    [pending, setPending] = useState(false),
    [filter, setFilter] = useState("");
  const lock = useRef(false);
  async function refresh() {
    const paths = leader
      ? ["/recolecciones", "/recolecciones/avisos"]
      : [
          "/community/collections",
          "/community/notifications",
          "/community/appointments",
          "/community/points",
        ];
    const [rows, notices, appointments, points] = await Promise.all(
      paths.map((p) => request(p, { token })),
    );
    setData({ rows, notices, appointments, points });
  }
  function report(e) {
    if (e.status === 401) end();
    else setError(e.message);
  }
  useEffect(() => {
    refresh().catch(report);
  }, [token]);
  async function run(path, body, key, success) {
    if (lock.current) return false;
    lock.current = true;
    setPending(true);
    setError("");
    setFeedback("");
    try {
      if (path) await request(path, { token, body, key });
      success?.();
      if (path) setFeedback("Cambios guardados.");
      await refresh();
      return true;
    } catch (e) {
      report(e);
      return false;
    } finally {
      lock.current = false;
      setPending(false);
    }
  }
  async function logout() {
    try {
      await request("/accounts/logout", { token, body: {} });
      end();
    } catch (e) {
      report(e);
    }
  }
  const rows = data?.rows || [],
    notices = data?.notices || [];
  const nav = [
    ["panel", leader ? "Bandeja" : "Mis recogidas", ClipboardList],
    ["avisos", "Avisos", Bell],
  ];
  return (
    <>
      <header>
        <Brand />
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline">{user.profile.full_name}</span>
          <button
            className="iconBtn"
            aria-label="Cerrar sesión"
            onClick={logout}
          >
            <LogOut size={19} />
          </button>
        </div>
      </header>
      <main className="shell">
        <div className="context">
          <MapPin size={15} /> Villas de San Pablo{" "}
          {isDemo && <strong>Demo</strong>}
        </div>
        <div className="heading">
          <div>
            <h1>{leader ? "Panel del colectivo" : "Mi comunidad"}</h1>
            <p className="muted">
              {leader
                ? "Gestión de recogidas · " +
                  (user.collective_id || "Colectivo asignado")
                : "Hola, " +
                  user.profile.full_name.split(" ")[0] +
                  ". Consulta y organiza tus recogidas."}
            </p>
          </div>
          {!leader && (
            <button className="primary" onClick={() => setTab("nueva")}>
              <Plus size={18} />
              Solicitar recogida
            </button>
          )}
        </div>
        <nav>
          {nav.map(([v, t, I]) => (
            <button
              key={v}
              aria-current={tab === v ? "page" : undefined}
              onClick={() => setTab(v)}
            >
              <I size={18} />
              {t}
            </button>
          ))}
          <button
            className="ml-auto"
            aria-label="Actualizar datos"
            disabled={pending}
            onClick={() => run()}
          >
            <RefreshCw size={17} />
          </button>
        </nav>
        {error && (
          <p role="alert">
            <CircleAlert size={18} aria-hidden="true" />
            {error}
          </p>
        )}
        {feedback && (
          <p role="status">
            <Check size={18} aria-hidden="true" />
            {feedback}
          </p>
        )}
        {tab === "nueva" && !leader ? (
          <RequestForm
            user={user}
            pending={pending}
            onCreate={(draft, clear) =>
              run("/recolecciones", draft.data, draft.key, () => {
                clear();
                setTab("panel");
              })
            }
          />
        ) : !data ? (
          <p>{error ? "No se pudieron cargar los datos." : "Cargando…"}</p>
        ) : tab === "avisos" ? (
          <section className="card">
            <h2>Avisos internos</h2>
            {!notices.length && <p className="muted">Aún no tienes avisos.</p>}
            {notices.map((n, i) => (
              <article className="notice" key={n.id || i}>
                <Bell size={18} />
                <div>
                  <b>{n.title || nameOf[n.evento] || n.evento}</b>
                  <p>
                    {n.message ||
                      rows.find((r) => r.id === n.solicitud_id)?.solicitud
                        ?.material}
                  </p>
                  {n.cita && <small>{date(n.cita)}</small>}
                  {n.motivo && <p>{n.motivo}</p>}
                </div>
              </article>
            ))}
          </section>
        ) : (
          <div className="contentGrid">
            <section>
              <div className="listTitle">
                <h2>
                  {leader ? "Solicitudes del colectivo" : "Mis solicitudes"}
                </h2>
                {leader && (
                  <select
                    aria-label="Filtrar por estado"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    <option value="">Todas</option>
                    {[
                      "recibida",
                      "revision",
                      "programada",
                      "recolectada",
                      "cancelada",
                    ].map((s) => (
                      <option key={s} value={s}>
                        {nameOf[s]}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {rows.filter((r) => !filter || r.estado === filter).length ===
                0 && (
                <div className="card empty">
                  <ClipboardList />
                  <h3>
                    {filter ? "Sin coincidencias" : "Aún no hay solicitudes"}
                  </h3>
                  <p className="muted">
                    {leader
                      ? "Las solicitudes asignadas a tu colectivo aparecerán aquí."
                      : "Solicita una recogida de residuos orgánicos o reciclables."}
                  </p>
                </div>
              )}
              {rows
                .filter((r) => !filter || r.estado === filter)
                .map((r) => (
                  <article className="card row" key={r.id}>
                    <CollectionStatus value={r.estado || r.status} />
                    <h3>
                      {r.description ||
                        r.solicitud?.material ||
                        r.entrega?.material}
                    </h3>
                    <p>
                      <MapPin size={16} />
                      {r.address || r.solicitud?.direccion || "Entrega directa"}
                    </p>
                    {leader && (
                      <>
                        {r.solicitud && (
                          <p>Disponibilidad: {r.solicitud.disponibilidad}</p>
                        )}
                        {r.cita && <p>{date(r.cita)}</p>}
                        {r.responsable && (
                          <small>Responsable de visita: {r.responsable}</small>
                        )}
                        <Actions row={r} run={run} pending={pending} />
                      </>
                    )}
                  </article>
                ))}
            </section>
            <aside>
              {leader ? (
                <div className="stat">
                  <Sprout />
                  <p>Solicitudes asignadas</p>
                  <b>{rows.length}</b>
                </div>
              ) : (
                <>
                  <div className="stat">
                    <Ticket />
                    <p>Mis puntos</p>
                    <b>{data.points.balance}</b>
                  </div>
                  <section className="card">
                    <CalendarDays />
                    <h3>Mis citas</h3>
                    {!data.appointments.length ? (
                      <p className="muted">
                        Aún no tienes visitas programadas.
                      </p>
                    ) : (
                      data.appointments.map((a) => (
                        <div className="appointment" key={a.collection_id}>
                          <b>{date(a.scheduled_at)}</b>
                          <p>Responsable: {a.responsible_name}</p>
                        </div>
                      ))
                    )}
                  </section>
                </>
              )}
            </aside>
          </div>
        )}
      </main>
    </>
  );
}

function App() {
  const [session, setSession] = useState(null),
    [loading, setLoading] = useState(true),
    [initError, setInitError] = useState("");
  function end() {
    sessionStorage.removeItem(sessionKey);
    setSession(null);
  }
  async function restore(token) {
    const user = await request("/accounts/me", { token });
    if (!["leader", "resident", "business"].includes(user.profile.role))
      throw Error("Este perfil no tiene acceso al panel.");
    sessionStorage.setItem(sessionKey, token);
    setSession({ token, user });
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
        setInitError(e.message);
      })
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <main className="shell">Cargando sesión…</main>;
  return session ? (
    <Dashboard {...session} end={end} />
  ) : (
    <>
      {initError && (
        <p role="alert">
          <CircleAlert size={18} aria-hidden="true" />
          {initError}
        </p>
      )}
      <Login
        onLogin={async (body) => {
          setInitError("");
          const login = await request("/accounts/login", { body });
          await restore(login.access_token);
        }}
      />
    </>
  );
}
createRoot(document.getElementById("root")).render(
  <>
    <App />
    <footer className="partners" aria-label="Identidad institucional">
      <img
        src="/marca/villas-de-san-pablo.png"
        alt="Villas de San Pablo"
        width="467"
        height="169"
      />
      <img
        src="/marca/santo-domingo.png"
        alt="Fundaci?n Santo Domingo"
        width="586"
        height="317"
      />
    </footer>
  </>,
);
