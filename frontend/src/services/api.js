import { demoRequest } from "../demo.js";

// Demo is opt-in for local workshops. A missing API URL always uses the real API.
const demoEnabled = import.meta.env.VITE_DEMO_MODE === "true";
const apiRoot = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
export const isDemo = demoEnabled;

export async function request(path, { token, body, key, method } = {}) {
  if (demoEnabled) return demoRequest(path, { token, body, key });

  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (key) headers["Idempotency-Key"] = key;

  const route = path.startsWith("/") ? path : `/${path}`;
  let response;
  try {
    response = await fetch(`${apiRoot}${route}`, {
      method: method || (body === undefined ? "GET" : "POST"),
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("No se pudo conectar con EcoConecta. Verifica que la API esté disponible e inténtalo de nuevo.");
  }
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : `No se pudo completar la operación (${response.status}).`,
    );
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}
