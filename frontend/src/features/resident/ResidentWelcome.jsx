import { ArrowRight, MapPin, Plus, Star } from "../../components/icons.jsx";

export function ResidentWelcome({ name, balance, canRequest, onRequest, onPoints }) {
  return (
    <div className="home-welcome">
      <header className="home-hero">
        <svg className="home-hero-art" viewBox="0 0 275 194" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" focusable="false">
          <path d="M52 144l36-39 43 13 27-47 49 19 37-54M131 118l42 43 53-27 18-98M158 71l-17-38 42-19M173 161l-23 26" />
          <circle cx="52" cy="144" r="5" /><circle cx="88" cy="105" r="6" /><circle cx="131" cy="118" r="7" />
          <circle cx="158" cy="71" r="6" /><circle cx="207" cy="90" r="7" /><circle cx="244" cy="36" r="6" />
          <circle cx="173" cy="161" r="5" /><circle cx="226" cy="134" r="7" />
          <path d="M194 62a47 47 0 1 1 52 77m-13-6 13 6-4 13" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div className="home-hero-copy">
          <p className="home-hero-location"><MapPin size={14} /> Villas de San Pablo</p>
          <h1>¡Hola, <span className="home-hero-name">{name}</span>!</h1>
          <p className="home-hero-subtitle">Separa, solicita tu recogida y suma puntos por tu barrio.</p>
          {Number.isFinite(balance) && (
            <button type="button" className="home-points-chip" onClick={onPoints}>
              <Star size={18} /> <span>{balance} {balance === 1 ? "punto" : "puntos"}</span>
            </button>
          )}
        </div>
      </header>
      <button type="button" className="home-cta" data-primary="true" disabled={!canRequest} onClick={onRequest}>
        <span className="home-cta-plus" aria-hidden="true"><Plus size={23} /></span>
        <span>Solicitar recogida</span>
        <ArrowRight size={22} className="home-cta-arrow" />
      </button>
      <div className="home-flow-hints">
        <span className="home-flow-chip">Orgánicos → huerteros</span>
        <span className="home-flow-chip" data-flow="recyclable">Reciclables → recicladores</span>
      </div>
    </div>
  );
}
