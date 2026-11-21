// Validaciones de registro y acceso con reglas colombianas.
// Siguen las reglas reales de FastAPI (accounts/service.py) sin endurecerlas.

export const collapseSpaces = (value = "") => value.replace(/\s+/g, " ").trim();

// Letras de cualquier idioma (tildes, ñ, ü), espacios, apóstrofo, guion y punto.
const NAME = /^[\p{L}\p{M}][\p{L}\p{M}'’.\- ]*$/u;

export function validateName(raw) {
  const value = collapseSpaces(raw);
  if (!value) return "Escribe tu nombre completo.";
  if (value.length > 160) return "El nombre es demasiado largo (máximo 160 caracteres).";
  if (!NAME.test(value)) return "Usa solo letras, espacios, apóstrofos o guiones.";
  if ((value.match(/\p{L}/gu) || []).length < 2) return "Escribe tu nombre completo.";
  return "";
}

// La API elimina puntos, guiones y espacios y exige de 1 a 20 dígitos.
export const normalizeNationalId = (value = "") => value.replace(/[.\-\s]/g, "");

export function validateNationalId(raw) {
  const value = normalizeNationalId(raw);
  if (!value) return "Escribe tu número de cédula.";
  if (!/^\d+$/.test(value)) return "La cédula solo puede tener números.";
  if (value.length > 20) return "La cédula no puede tener más de 20 dígitos.";
  return "";
}

// Acepta +57, 0057 o 57 delante y separadores comunes; devuelve 10 dígitos.
export function normalizePhone(raw = "") {
  let digits = raw.replace(/[\s().\-]/g, "");
  if (digits.startsWith("+57")) digits = digits.slice(3);
  else if (digits.startsWith("0057")) digits = digits.slice(4);
  else if (digits.length === 12 && digits.startsWith("57")) digits = digits.slice(2);
  return digits;
}

export function validateMobile(raw) {
  const value = normalizePhone(raw);
  if (!value) return "Escribe tu número de celular.";
  if (/[^\d+]/.test(value)) return "Usa solo números. Ejemplo: 300 123 4567.";
  if (!value.startsWith("3")) return "El celular debe empezar por 3. Ejemplo: 300 123 4567.";
  if (value.length !== 10) return `El celular debe tener 10 dígitos (tiene ${value.length}).`;
  return "";
}

// Muestra 3001234567 como 300 123 4567.
export const formatPhone = (value = "") =>
  /^\d{10}$/.test(value) ? `${value.slice(0, 3)} ${value.slice(3, 6)} ${value.slice(6)}` : value;

export function validatePin(pin) {
  if (!pin) return "Escribe un PIN.";
  if (!/^\d+$/.test(pin)) return "El PIN solo puede tener números.";
  if (pin.length < 4 || pin.length > 12) return "El PIN debe tener entre 4 y 12 números.";
  return "";
}
