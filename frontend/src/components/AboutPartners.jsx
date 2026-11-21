// «Acerca de EcoConecta»: logos aliados originales, en un único lugar discreto
// (no se repiten en el pie de cada pantalla).
export function AboutPartners() {
  return (
    <section className="about-partners" aria-labelledby="about-title">
      <h2 id="about-title" className="about-title">Acerca de EcoConecta</h2>
      <p className="muted">Iniciativa comunitaria de Villas de San Pablo, Barranquilla, en alianza con:</p>
      <div className="about-logos">
        <img src="/marca/villas-de-san-pablo.png" alt="Villas de San Pablo" width="467" height="169" />
        <img src="/marca/santo-domingo.png" alt="Fundación Santo Domingo" width="586" height="317" />
      </div>
    </section>
  );
}
