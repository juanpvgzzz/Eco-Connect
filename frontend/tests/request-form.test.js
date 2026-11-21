// Regresión: "Solicitar recogida" dejaba la pantalla en blanco cuando la app
// se abría por HTTP fuera de localhost, porque RequestForm llamaba a
// crypto.randomUUID() (solo disponible en contextos seguros) al renderizar.
import { test, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToString } from "react-dom/server";

let vite, RequestForm, newIdempotencyKey, CollectionStatus;
const realCrypto = globalThis.crypto;
const user = {
  id: "u1",
  profile: { phone: "3001234567", address: "Calle 10 # 20-30", kind: "household", full_name: "Ana Pérez" },
};

function storage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
}
function insecureContext() {
  // Igual que un navegador fuera de HTTPS/localhost: sin randomUUID.
  Object.defineProperty(globalThis, "crypto", {
    configurable: true,
    value: { getRandomValues: (a) => webcrypto.getRandomValues(a) },
  });
}
const render = () => renderToString(createElement(RequestForm, { user, onCreate() {}, onCancel() {} }));

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
  ({ RequestForm } = await vite.ssrLoadModule("/src/features/collections/RequestForm.jsx"));
  ({ newIdempotencyKey } = await vite.ssrLoadModule("/src/utils/idempotency.js"));
  ({ CollectionStatus } = await vite.ssrLoadModule("/src/components/CollectionStatus.jsx"));
});
after(() => vite?.close());
beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: realCrypto });
  globalThis.sessionStorage = storage();
});

test("RequestForm se renderiza sin crypto.randomUUID (contexto no seguro)", () => {
  insecureContext();
  const html = render();
  assert.match(html, /Nueva solicitud/);
  assert.match(html, /Residuos orgánicos/);
  assert.match(html, /Residuos reciclables/);
});

test("RequestForm ignora un borrador corrupto en sessionStorage", () => {
  sessionStorage.setItem("eco.api.session.request.u1", "{no es json");
  assert.match(render(), /Nueva solicitud/);
  sessionStorage.setItem("eco.api.session.request.u1", JSON.stringify({ residuo: "organico" }));
  assert.match(render(), /Nueva solicitud/);
  // Borrador del formulario anterior ({ key, data }): se descarta sin romper.
  sessionStorage.setItem("eco.api.session.request.u1", JSON.stringify({ key: "k", data: { residuo: "organico" } }));
  assert.match(render(), /Nueva solicitud/);
});

test("newIdempotencyKey genera UUID v4 únicos sin randomUUID", () => {
  insecureContext();
  const a = newIdempotencyKey(), b = newIdempotencyKey();
  assert.match(a, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.notEqual(a, b);
});

// Regresión: tras crear la solicitud, "Mis solicitudes" quedaba en blanco
// porque CollectionStatus usaba nameOf sin importarlo.
test("CollectionStatus traduce el estado de una solicitud recién creada", () => {
  assert.match(renderToString(createElement(CollectionStatus, { value: "recibida" })), /Recibida/);
  assert.match(renderToString(createElement(CollectionStatus, { value: "received" })), /Recibida/);
});
