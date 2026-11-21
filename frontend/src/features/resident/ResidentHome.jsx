import { ArrowLeft, BookOpen, CalendarDays, ChevronRight, ClipboardList, Sprout, Star } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { ErrorBoundary } from "../../components/ErrorBoundary.jsx";
import { stageOf } from "../../utils/format.js";
import { NoticesView } from "../notices/NoticesView.jsx";
import { RequestForm } from "../collections/RequestForm.jsx";
import { RequestCard } from "./RequestCard.jsx";
import { Profile } from "./Profile.jsx";
import { EducationLibrary } from "./EducationLibrary.jsx";
import { NextPickup } from "./NextPickup.jsx";
import { CalendarView } from "./CalendarView.jsx";
import { PointsView } from "./PointsView.jsx";
import { HistoryView } from "./HistoryView.jsx";
import { ResidentWelcome } from "./ResidentWelcome.jsx";

const RECENT = 3;
const HOME_LINKS = [
  { id: "historial", title: "Mis solicitudes", description: "Consulta el estado.", icon: ClipboardList },
  { id: "citas", title: "Mis citas", description: "Consulta tus visitas.", icon: CalendarDays },
  { id: "puntos", title: "Mis puntos", description: "Saldo y movimientos.", icon: Star },
  { id: "educacion", title: "Guía ambiental", description: "Separa tus residuos.", icon: BookOpen },
];

export function ResidentHome({ user, data, notices, view, setView, seen, onCreate, created, clearCreated, logout, token }) {
  const back = () => setView("inicio");
  // RN-08: hogares y unidades productivas solicitan solo si administración los habilitó.
  const canRequest = Boolean(user.profile.pilot_enabled);
  const pendingTitle = user.profile.kind === "business" ? "Unidad productiva pendiente de habilitación" : "Hogar pendiente de habilitación";
  const rows = data?.rows || [];
  const appointments = data?.appointments || [];
  const wrap = (content) => <div className="page view">{content}</div>;

  if (view === "nueva") return wrap(canRequest
    ? <RequestForm user={user} onCreate={onCreate} onCancel={back} />
    : <Alert tone="warning" title={pendingTitle}>
        Una persona administradora debe autorizar esta cuenta para el piloto antes de enviar solicitudes.
        <Button variant="ghost" onClick={back}>Volver al inicio</Button>
      </Alert>);
  if (view === "perfil") return wrap(<Profile user={user} onBack={back} onLogout={logout} />);
  if (view === "avisos") return wrap(<NoticesView notices={notices} seen={seen} onBack={back} />);
  if (view === "educacion") return <EducationLibrary onBack={back} />;
  if (!data && view !== "inicio") return wrap(
    <section className="subview">
      <div className="view-head"><Button variant="secondary" icon={ArrowLeft} onClick={back}>Inicio</Button></div>
      <Loading>Cargando tus recogidas…</Loading>
    </section>,
  );
  if (view === "citas") return wrap(<CalendarView appointments={appointments} rows={rows} onBack={back} />);
  if (view === "puntos") return wrap(<PointsView points={data.points} movements={data.movements || []} token={token} onBack={back} />);
  if (view === "historial")
    return wrap(<HistoryView rows={rows} appointments={appointments} freshId={created} onNew={canRequest ? () => setView("nueva") : undefined} onBack={back} token={token} />);

  const firstName = user.profile.full_name.split(" ")[0];
  const pending = rows.filter((r) => ["pending", "review"].includes(stageOf[r.status])).length;
  const byRequest = Object.fromEntries(appointments.map((a) => [a.collection_id, a]));
  const openView = (id) => () => {
    setView(id);
    requestAnimationFrame(() => document.getElementById("contenido")?.focus({ preventScroll: true }));
  };
  const openRequest = openView("nueva");
  const openHistory = openView("historial");

  return (
    <div className="page view resident-home">
      <ResidentWelcome
        name={firstName}
        balance={data?.points?.balance}
        canRequest={canRequest}
        onRequest={openRequest}
        onPoints={openView("puntos")}
      />

      {!canRequest && (
        <Alert tone="warning" title={pendingTitle}>
          Una persona administradora debe autorizar esta cuenta para el piloto antes de enviar solicitudes.
        </Alert>
      )}
      {created && (
        <Alert tone="success" title="¡Solicitud recibida correctamente!" onClose={clearCreated}>
          Ya aparece en “Mis solicitudes”. El colectivo te avisará cuando programe la visita.
        </Alert>
      )}

      {!data && <div className="visually-hidden"><Loading>Cargando tus recogidas…</Loading></div>}
      <div className="home-content">
        <div className="home-content-primary">
          {data
            ? <NextPickup appointments={appointments} pending={pending} onDetails={openHistory} />
            : <div className="home-skeleton home-skeleton-pickup animate-pulse" aria-hidden="true" />}
          <section className="home-section home-quick-section">
            <h2>Accesos rápidos</h2>
            <nav className="resident-shortcuts" aria-label="Accesos del inicio">
              {HOME_LINKS.map(({ id, title, description, icon: Icon }) => (
                <button key={id} type="button" className="resident-shortcut" data-shortcut={id} onClick={openView(id)}>
                  <span className="resident-shortcut-top" aria-hidden="true">
                    <span className="resident-shortcut-icon"><Icon size={22} /></span>
                    <ChevronRight size={18} />
                  </span>
                  <span>
                    <span className="resident-shortcut-title">{title}</span>
                    <span className="resident-shortcut-description">{description}</span>
                  </span>
                </button>
              ))}
            </nav>
          </section>
        </div>

        <section className="home-section home-recent" aria-labelledby="recent-title">
          <div className="home-section-heading">
            <h2 id="recent-title" className="home-section-title">Solicitudes recientes</h2>
            <button type="button" className="home-text-action" onClick={openHistory}>Ver todas</button>
          </div>
          {!data ? (
            <div className="request-list" aria-hidden="true">
              <div className="home-skeleton animate-pulse" />
              <div className="home-skeleton animate-pulse" />
            </div>
          ) : rows.length ? (
            <ErrorBoundary message="No se pudieron mostrar tus solicitudes.">
              <div className="request-list">
                {rows.slice(0, RECENT).map((row) => (
                  <RequestCard key={row.id} row={row} appointment={byRequest[row.id]} showVisitInSummary={false} fresh={row.id === created} token={token} recent />
                ))}
              </div>
            </ErrorBoundary>
          ) : (
            <EmptyState icon={Sprout} title="Aún no tienes solicitudes" action={canRequest && (
              <Button variant="secondary" onClick={openRequest}>Crear solicitud</Button>
            )} />
          )}
        </section>
      </div>
    </div>
  );
}
