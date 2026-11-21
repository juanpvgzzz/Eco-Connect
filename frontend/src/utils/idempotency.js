// crypto.randomUUID solo existe en contextos seguros (HTTPS o localhost).
// Si la app se abre por HTTP desde otra máquina (p. ej. http://192.168.x.x),
// llamarlo lanza TypeError durante el render y la pantalla queda en blanco.
// crypto.getRandomValues sí está disponible en cualquier contexto.
export function newIdempotencyKey() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; // versión 4
  b[8] = (b[8] & 0x3f) | 0x80; // variante RFC 4122
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
