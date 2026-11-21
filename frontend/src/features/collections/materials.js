// Sugerencias rápidas por tipo de residuo. El catálogo oficial de materiales lo
// usa el colectivo al cerrar la entrega; aquí el vecino solo describe lo que tiene.
import { Recycle, Sprout } from "../../components/icons.jsx";

export const WASTE_TYPES = {
  organico: {
    title: "Residuos orgánicos",
    short: "Orgánico",
    description: "Restos vegetales y materiales orgánicos admitidos.",
    examples: ["Cáscaras de frutas y verduras", "Restos de verduras crudas", "Borra de café", "Hojas y poda"],
    icon: Sprout,
    tone: "organic",
    team: "Huerta comunitaria",
  },
  reciclable: {
    title: "Residuos reciclables",
    short: "Reciclable",
    description: "Papel, cartón, plástico, vidrio y otros materiales admitidos.",
    examples: ["Papel", "Cartón", "Botellas plásticas", "Vidrio", "Latas"],
    icon: Recycle,
    tone: "recycle",
    team: "Colectivo de reciclaje",
  },
};

export function describeMaterial({ picks = [], detail = "" }) {
  const text = detail.replace(/\s+/g, " ").trim();
  if (picks.length && text) return `${picks.join(", ")}. ${text}`;
  return picks.length ? picks.join(", ") : text;
}
