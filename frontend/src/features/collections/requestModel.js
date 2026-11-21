// Estado del asistente "Solicitar recogida" y conversión al contrato de
// POST /recolecciones (Request: residuo, material, contacto, direccion,
// generador, disponibilidad, observaciones). El contrato no cambia.
import { emptyAddress, formatAddress, validateAddress } from "../address/address.js";
import { normalizePhone, validateMobile } from "../auth/validation.js";
import { describeAvailability, validateAvailability } from "./availability.js";
import { describeMaterial } from "./materials.js";
import { newIdempotencyKey } from "../../utils/idempotency.js";

export const REQUEST_STEPS = ["Residuo", "Recogida", "Confirmar"];

export function emptyRequest(user) {
  return {
    residuo: "organico",
    picks: [],
    detail: "",
    useOwnAddress: true,
    address: emptyAddress(),
    contact: user.profile.phone || "",
    days: [],
    slots: [],
    note: "",
    observaciones: "",
  };
}

export const newDraft = (user) => ({ key: newIdempotencyKey(), step: 0, form: emptyRequest(user) });

export function toPayload(form, user) {
  return {
    residuo: form.residuo,
    material: describeMaterial(form),
    contacto: normalizePhone(form.contact),
    direccion: form.useOwnAddress ? user.profile.address : formatAddress(form.address),
    generador: user.profile.kind === "business" ? "unidad_productiva" : "hogar",
    disponibilidad: describeAvailability(form),
    observaciones: form.observaciones.replace(/\s+/g, " ").trim(),
  };
}

export function validateStep(step, form) {
  if (step === 0) {
    const material = describeMaterial(form);
    if (!material) return { material: "Elige o describe al menos un material." };
    if (material.length > 500) return { material: "La descripción es demasiado larga (máximo 500 caracteres)." };
    return {};
  }
  if (step === 1) {
    const errors = { contact: validateMobile(form.contact), ...validateAvailability(form) };
    if (!form.useOwnAddress) Object.assign(errors, validateAddress(form.address));
    if (form.observaciones.length > 2000) errors.observaciones = "Máximo 2000 caracteres.";
    return Object.fromEntries(Object.entries(errors).filter(([, v]) => v));
  }
  return {};
}

// Borrador en sessionStorage (nunca contiene el PIN). Un borrador antiguo,
// corrupto o con otra forma se descarta en lugar de romper la pantalla.
export function readDraft(storageKey) {
  try {
    const draft = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    return draft?.key && draft.form && typeof draft.step === "number" ? draft : null;
  } catch {
    return null;
  }
}

export function writeDraft(storageKey, draft) {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(draft));
  } catch {
    // Sin almacenamiento (modo privado): el asistente sigue funcionando en memoria.
  }
}
