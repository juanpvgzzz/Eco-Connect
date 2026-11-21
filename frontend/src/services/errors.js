// Traduce los errores de la API (algunos llegan en inglés) a mensajes claros.
const KNOWN = {
  "Invalid national ID or PIN": "La cédula o el PIN no coinciden. Revísalos e inténtalo de nuevo.",
  "Too many login attempts; try again later": "Hiciste demasiados intentos. Espera unos minutos y vuelve a intentarlo.",
  "An account with this national ID already exists": "Ya existe una cuenta con esta cédula. Inicia sesión con tu PIN.",
  "Invalid or expired session": "Tu sesión terminó. Vuelve a iniciar sesión.",
  "Authentication required": "Tu sesión terminó. Vuelve a iniciar sesión.",
  "Insufficient permissions": "Tu perfil no tiene permiso para esta acción.",
  "This business is not enabled for the pilot": "Tu unidad productiva aún no está habilitada para el piloto.",
  "Cliente fuera del piloto": "Tu cuenta aún no está habilitada para el piloto. Una persona administradora debe autorizarla.",
  "Invalid request": "Algunos datos no son válidos. Revisa el formulario.",
  "Sin responsable de turno para esa cita": "No hay un responsable de turno en esa fecha y hora. Elige otro horario.",
};

export function friendlyError(error) {
  const message = error?.message || "";
  if (KNOWN[message]) return KNOWN[message];
  if (error?.status === 401) return KNOWN["Invalid or expired session"];
  if (error?.status === 429) return KNOWN["Too many login attempts; try again later"];
  if (error?.status === 422) return KNOWN["Invalid request"];
  if (error?.status >= 500) return "El servicio no respondió. Inténtalo de nuevo en unos minutos.";
  return message || "No se pudo completar la operación. Inténtalo de nuevo.";
}
