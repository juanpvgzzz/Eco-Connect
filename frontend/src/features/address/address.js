// Dirección colombiana estructurada → texto canónico.
// La API guarda la dirección como texto (máx. 240), así que no se cambia el modelo.

export const STREET_TYPES = ["Calle", "Carrera", "Diagonal", "Transversal", "Avenida Calle", "Avenida Carrera"];
export const COMPLEMENT_TYPES = ["Apartamento", "Interior", "Piso", "Bloque", "Torre", "Casa"];
export const DEFAULT_SECTOR = "Villas de San Pablo";
export const CITY = "Barranquilla";
export const MAX_ADDRESS = 240;

export const emptyAddress = () => ({
  mode: "block",
  streetType: "Calle", number: "", letter: "", cross: "", crossSuffix: "", plate: "",
  complementType: "Apartamento", complement: "",
  manzana: "", casa: "", bloque: "", apto: "", conjunto: "",
  sector: DEFAULT_SECTOR, references: "",
  custom: null,
});

const clean = (v = "") => v.replace(/\s+/g, " ").trim();
// "45" + "A" → "45A"; "45" + "Bis" → "45 Bis"
const withSuffix = (base, suffix) => {
  const s = clean(suffix);
  if (!s) return clean(base);
  return /^[A-Za-zÑñ]$/.test(s) ? clean(base) + s.toUpperCase() : `${clean(base)} ${s}`;
};

export function formatAddress(a) {
  if (a.custom !== null && a.custom !== undefined) return clean(a.custom);
  const parts = [];
  if (a.mode === "street") {
    const main = `${a.streetType} ${withSuffix(a.number, a.letter)}`;
    const cross = clean(a.cross) ? ` # ${withSuffix(a.cross, a.crossSuffix)}` : "";
    const plate = clean(a.plate) ? `-${clean(a.plate)}` : "";
    parts.push(clean(main + cross + plate));
    if (clean(a.complement)) parts.push(`${a.complementType} ${clean(a.complement)}`);
  } else {
    if (clean(a.manzana)) parts.push(`Manzana ${clean(a.manzana)}`);
    if (clean(a.casa)) parts.push(`Casa ${clean(a.casa)}`);
    if (clean(a.bloque)) parts.push(`Bloque ${clean(a.bloque)}`);
    if (clean(a.apto)) parts.push(`Apartamento ${clean(a.apto)}`);
    if (clean(a.conjunto)) parts.push(clean(a.conjunto));
  }
  const sector = clean(a.sector);
  if (sector && !parts.some((p) => p.toLowerCase() === sector.toLowerCase())) parts.push(sector);
  parts.push(CITY);
  let text = parts.filter(Boolean).join(", ");
  if (clean(a.references)) text += `. Referencia: ${clean(a.references)}`;
  return text;
}

// Valores alfanuméricos cortos: admite 45, 45A, 12B Bis, 8-1, Sur, Este…
const TOKEN = /^[0-9A-Za-zÑñ][0-9A-Za-zÑñ .\-]{0,14}$/;

export function validateAddress(a) {
  const errors = {};
  const need = (field, label) => {
    if (!clean(a[field])) errors[field] = `Escribe ${label}.`;
    else if (!TOKEN.test(clean(a[field]))) errors[field] = "Usa números, letras o guiones.";
  };
  if (a.custom !== null && a.custom !== undefined) {
    const text = clean(a.custom);
    if (text.length < 5) errors.custom = "La dirección es demasiado corta.";
    else if (text.length > MAX_ADDRESS) errors.custom = `Máximo ${MAX_ADDRESS} caracteres (tiene ${text.length}).`;
    return errors;
  }
  if (a.mode === "street") {
    need("number", "el número de la vía");
    need("cross", "el número de la vía secundaria");
    need("plate", "el número de placa");
  } else {
    need("manzana", "la manzana");
    need("casa", "la casa o el lote");
  }
  if (!clean(a.sector)) errors.sector = "Escribe el barrio o sector.";
  const length = formatAddress(a).length;
  if (length > MAX_ADDRESS) errors.references = `La dirección completa supera ${MAX_ADDRESS} caracteres. Acorta las referencias.`;
  return errors;
}
