import { demoRequest } from "./demo.js";

const origin = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
export const isDemo = !origin;

export async function request(path, { token, body, key } = {}) {
  if (isDemo) return demoRequest(path, { token, body, key });
  const headers = {};
  if (token) headers.Authorization = "Bearer " + token;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (key) headers["Idempotency-Key"] = key;
  const response = await fetch(origin + path, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : "No se pudo completar la operación (" + response.status + ").",
    );
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}
