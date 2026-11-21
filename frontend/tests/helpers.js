// Carga módulos del frontend con la misma transformación que Vite (JSX
// automático, import.meta.env) sin navegador ni dependencias nuevas.
import { createServer } from "vite";

let server;
export async function load(path) {
  server ??= await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
  return server.ssrLoadModule(path);
}
export const close = () => server?.close();

export function memoryStorage() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
  };
}
