import { useEffect, useState } from "react";
import { ArrowLeft, BadgeCheck, CircleCheck, Star, Ticket } from "../../components/icons.jsx";
import { Alert } from "../../components/ui/Alert.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { Card } from "../../components/ui/Card.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Loading } from "../../components/ui/Spinner.jsx";
import { request } from "../../services/api.js";
import { friendlyError } from "../../services/errors.js";
import { formatDate, formatDay } from "../../utils/format.js";

const formatNumber = new Intl.NumberFormat("es-CO");

function Participation({ completed, milestones }) {
  const obtained = milestones.filter((milestone) => milestone.unlocked_at);
  const next = milestones.find((milestone) => milestone.pickups > completed);
  const remaining = next ? next.pickups - completed : 0;

  return <>
    <Card className="stack" aria-labelledby="points-progress-title">
      <h2 id="points-progress-title">Próxima insignia</h2>
      {next ? <>
        <p><strong>{next.title}</strong></p>
        <progress className="points-progress" aria-label={`Progreso hacia ${next.title}`} value={completed} max={next.pickups} />
        <p>{completed} de {next.pickups} recogidas. {remaining === 1 ? "Falta 1 recogida." : `Faltan ${remaining} recogidas.`}</p>
      </> : <p>Ya obtuviste todas las insignias de participación.</p>}
    </Card>
    <Card className="stack" aria-labelledby="points-badges-title">
      <h2 id="points-badges-title">Insignias obtenidas</h2>
      <p className="muted">Reconocimientos digitales y gratuitos por tus recogidas completadas.</p>
      {obtained.length > 0 ? <ul className="grid gap-3 sm:grid-cols-2">
        {obtained.map((badge) => <li className="points-badge" key={badge.pickups}>
          <BadgeCheck size={25} aria-hidden="true" />
          <div>
            <strong>{badge.title}</strong>
            <p className="muted">{badge.pickups} {badge.pickups === 1 ? "recogida" : "recogidas"} · <time dateTime={badge.unlocked_at}>{formatDay(badge.unlocked_at)}</time></p>
          </div>
        </li>)}
      </ul> : <p>Aún no tienes insignias.</p>}
    </Card>
  </>;
}

function Rewards({ rewards, balance, token }) {
  const [codes, setCodes] = useState({});
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  async function requestCode(rewardId) {
    setBusy(rewardId);
    setError("");
    try {
      const code = await request("/community/redemptions", { token, body: { reward_id: rewardId } });
      setCodes((current) => ({ ...current, [rewardId]: code }));
    } catch (cause) { setError(friendlyError(cause)); }
    finally { setBusy(null); }
  }

  return <Card className="stack" aria-labelledby="points-rewards-title">
    <h2 id="points-rewards-title">Recompensas</h2>
    {rewards.length ? <ul className="grid gap-3 sm:grid-cols-2">
      {rewards.map((reward) => {
        const code = codes[reward.id];
        return <li className="points-reward stack" key={reward.id}>
          <h3>{reward.title}</h3>
          <p>{reward.description}</p>
          <p><strong>{formatNumber.format(reward.cost)} puntos</strong> · {reward.stock} {reward.stock === 1 ? "disponible" : "disponibles"}</p>
          {code && <Alert tone="success" title="Tu código de canje">
            <p className="data wrap-anywhere">{code.code}</p>
            <p>Preséntalo a la coordinación de huerta. Vence el {formatDate(code.expires_at)}.</p>
          </Alert>}
          {(!code || Date.parse(code.expires_at) <= Date.now()) && (
            balance < reward.cost || balance == null ? <p className="muted">{balance == null ? "Consulta tu saldo para solicitar un código." : "Saldo insuficiente para este canje."}</p>
              : <div><Button loading={busy === reward.id} disabled={busy !== null} onClick={() => requestCode(reward.id)}>Solicitar código de canje</Button></div>
          )}
        </li>;
      })}
    </ul> : <p><strong>Próximamente.</strong> Aquí aparecerán las recompensas habilitadas y validadas.</p>}
    {error && <Alert tone="error">{error}</Alert>}
  </Card>;
}

export function PointsView({ points, movements, token, onBack }) {
  const [snapshot, setSnapshot] = useState(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    const get = (path) => request(`/community/${path}`, { token });
    Promise.allSettled([get("points"), get("points/movements"), get("points/participation"), get("rewards")])
      .then(([balance, history, participation, rewards]) => {
        if (!active) return;
        setSnapshot({
          balance: balance.value?.balance,
          history: history.value,
          participation: participation.value,
          rewards: rewards.value,
          error: [balance, history, participation, rewards].some((result) => result.status === "rejected"),
        });
      });
    return () => { active = false; };
  }, [retry, token]);

  const balance = snapshot?.balance ?? points?.balance;
  const history = snapshot?.history ?? movements;
  const completed = snapshot?.participation?.completed;
  const earned = history.reduce((total, movement) => total + Math.max(0, movement.points), 0);
  return (
    <section className="subview enter points-view" aria-labelledby="points-title">
      <div className="view-head">
        <h1 id="points-title">Mis puntos</h1>
        <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Inicio</Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="points-balance">
          <span className="points-icon"><Star size={28} aria-hidden="true" /></span>
          <div>
            <p className="points-value data">{balance == null ? "—" : formatNumber.format(balance)}</p>
            <p className="points-label">puntos disponibles</p>
            {snapshot?.history && <p className="muted">{formatNumber.format(earned)} puntos ganados en total</p>}
          </div>
        </div>
        <div className="points-balance points-pickups">
          <span className="points-icon"><CircleCheck size={28} aria-hidden="true" /></span>
          <div>
            <p className="points-value data">{completed == null ? "—" : formatNumber.format(completed)}</p>
            <p className="points-label">{completed === 1 ? "recogida realizada" : "recogidas realizadas"}</p>
          </div>
        </div>
      </div>
      <p className="muted">Los hitos de participación, las recompensas y sus costos son propuestas sujetas a validación de la Fundación Santo Domingo.</p>
      {!snapshot && <Loading>Consultando puntos y recompensas…</Loading>}
      {snapshot?.error && <Alert tone="error" title="Algunos datos de Mis puntos no se pudieron actualizar">
        <Button variant="ghost" onClick={() => { setSnapshot(null); setRetry((attempt) => attempt + 1); }}>Reintentar</Button>
      </Alert>}
      {snapshot?.participation && <Participation {...snapshot.participation} />}
      {snapshot?.rewards && <Rewards rewards={snapshot.rewards} balance={balance} token={token} />}
      <h2 className="home-section-title">Historial de puntos</h2>
      {history.length ? (
        <ul className="movement-list">
          {history.map((m) => (
            <li key={m.id} className="movement">
              <span className="movement-icon" data-tone={m.points > 0 ? "in" : "out"}>{m.points > 0 ? <Star size={20} /> : <Ticket size={20} />}</span>
              <div className="movement-body">
                <p className="movement-title">{m.points > 0 ? "Puntos por entrega" : "Canje de puntos"}</p>
                <time className="muted" dateTime={m.created_at}>{formatDate(m.created_at)}</time>
              </div>
              <span className="movement-amount data" data-tone={m.points > 0 ? "in" : "out"}>{m.points > 0 ? "+" : ""}{m.points}</span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon={Star} title="Aún no tienes movimientos">
          Recibirás puntos cuando el colectivo cierre una recogida entregada.
        </EmptyState>
      )}
    </section>
  );
}
