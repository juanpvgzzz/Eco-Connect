import { useEffect } from "react";
import { ArrowLeft } from "../../components/icons.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { NoticeList } from "./NoticeList.jsx";

// Vista completa de avisos del vecino. Al salir, los avisos mostrados dejan de
// marcarse como «Nuevo» en este dispositivo (la API aún no guarda la lectura).
export function NoticesView({ notices, seen, onBack }) {
  useEffect(() => () => seen.setSeenAt(seen.markSeen()), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <section className="notices-view enter" aria-labelledby="avisos-title">
      <div className="view-head">
        <div>
          <h1 id="avisos-title">Avisos</h1>
          <p className="muted">Cambios en tus solicitudes y puntos acreditados.</p>
        </div>
        <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Volver</Button>
      </div>
      <NoticeList
        notices={notices}
        isNew={seen.isNew}
        action={(n) => (n.kind === "points" || n.kind === "redeemed" ? null : { label: "Ver mis solicitudes", onClick: onBack })}
      />
    </section>
  );
}
