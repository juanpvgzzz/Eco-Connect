// Reglas de los formularios: validaciones colombianas, dirección estructurada,
// disponibilidad y conversión al contrato de POST /recolecciones.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { close, load, memoryStorage } from "./helpers.js";

let v, addr, avail, model;
before(async () => {
  v = await load("/src/features/auth/validation.js");
  addr = await load("/src/features/address/address.js");
  avail = await load("/src/features/collections/availability.js");
  model = await load("/src/features/collections/requestModel.js");
});
after(close);

test("nombre: normaliza espacios y admite tildes, ñ, apóstrofos y guiones", () => {
  assert.equal(v.collapseSpaces("  Ana   María  Núñez "), "Ana María Núñez");
  for (const ok of ["Ana María Núñez", "José D'Alessandro", "María-José Güell", "Ñañez"]) assert.equal(v.validateName(ok), "", ok);
  assert.match(v.validateName("   "), /nombre completo/);
  assert.match(v.validateName("Ana 123"), /solo letras/);
  assert.match(v.validateName("A"), /nombre completo/);
});

test("cédula: quita puntos y espacios, solo números, máximo 20 dígitos (regla de la API)", () => {
  assert.equal(v.normalizeNationalId(" 1.234.567-8 "), "12345678");
  assert.equal(v.validateNationalId("1.234.567"), "");
  assert.match(v.validateNationalId("12A45"), /solo puede tener números/);
  assert.match(v.validateNationalId("1".repeat(21)), /20 dígitos/);
  assert.match(v.validateNationalId(""), /cédula/);
});

test("celular: 10 dígitos que empiezan por 3; normaliza +57 y separadores", () => {
  for (const raw of ["3001234567", "+57 300 123 4567", "300-123-4567", "(300) 123 4567", "573001234567", "0057 3001234567"]) {
    assert.equal(v.normalizePhone(raw), "3001234567", raw);
    assert.equal(v.validateMobile(raw), "", raw);
  }
  assert.match(v.validateMobile("6053456789"), /empezar por 3/);
  assert.match(v.validateMobile("30012345"), /10 dígitos \(tiene 8\)/);
  assert.match(v.validateMobile("300abc4567"), /solo números/);
  assert.equal(v.formatPhone("3001234567"), "300 123 4567");
});

test("PIN: 4 a 12 números, como exige FastAPI", () => {
  assert.equal(v.validatePin("1234"), "");
  assert.match(v.validatePin("12a4"), /solo puede tener números/);
  assert.match(v.validatePin("123"), /entre 4 y 12/);
  assert.match(v.validatePin("1".repeat(13)), /entre 4 y 12/);
});

test("dirección vial: genera nomenclatura canónica colombiana", () => {
  const a = { ...addr.emptyAddress(), mode: "street", streetType: "Carrera", number: "45", cross: "68", plate: "32", complement: "301" };
  assert.equal(addr.formatAddress(a), "Carrera 45 # 68-32, Apartamento 301, Villas de San Pablo, Barranquilla");
  const b = { ...a, streetType: "Calle", number: "45", letter: "a", cross: "68", crossSuffix: "Bis", complement: "" };
  assert.equal(addr.formatAddress(b), "Calle 45A # 68 Bis-32, Villas de San Pablo, Barranquilla");
  assert.deepEqual(addr.validateAddress(a), {});
  const missing = addr.validateAddress({ ...a, cross: "", plate: "" });
  assert.ok(missing.cross && missing.plate);
});

test("dirección por manzana: Manzana 12, Casa 08 y campos opcionales", () => {
  const a = { ...addr.emptyAddress(), manzana: "12", casa: "08" };
  assert.equal(addr.formatAddress(a), "Manzana 12, Casa 08, Villas de San Pablo, Barranquilla");
  const full = { ...a, bloque: "3", apto: "202", conjunto: "Conjunto Los Almendros", references: "frente al parque" };
  assert.equal(
    addr.formatAddress(full),
    "Manzana 12, Casa 08, Bloque 3, Apartamento 202, Conjunto Los Almendros, Villas de San Pablo, Barranquilla. Referencia: frente al parque",
  );
  assert.ok(addr.validateAddress({ ...a, casa: "" }).casa);
});

test("dirección: el texto editado a mano tiene prioridad y no se rechaza por su nomenclatura", () => {
  const a = { ...addr.emptyAddress(), custom: "  Km 5 vía al mar, parcela La Esperanza  " };
  assert.equal(addr.formatAddress(a), "Km 5 vía al mar, parcela La Esperanza");
  assert.deepEqual(addr.validateAddress(a), {});
  assert.ok(addr.validateAddress({ ...a, custom: "x".repeat(241) }).custom);
});

test("disponibilidad: días y franjas se serializan a texto claro (no es una cita)", () => {
  assert.equal(
    avail.describeAvailability({ days: ["lun", "mie"], slots: ["manana"], note: " después de las 9 " }),
    "Lunes y Miércoles · Mañana (7:00 a. m. a 12:00 m.) · Nota: después de las 9",
  );
  assert.match(avail.describeAvailability({ days: avail.DAYS.map((d) => d.id), slots: ["manana", "tarde"] }), /^Todos los días · Mañana .* y Tarde/);
  assert.deepEqual(Object.keys(avail.validateAvailability({ days: [], slots: [] })).sort(), ["days", "slots"]);
});

test("solicitud: toPayload respeta el contrato existente de POST /recolecciones", () => {
  const user = { profile: { address: "Manzana 1, Casa 2", phone: "3001234567", kind: "household" } };
  const form = { ...model.emptyRequest(user), residuo: "reciclable", picks: ["Cartón"], detail: "dos cajas", days: ["sab"], slots: ["tarde"], contact: "+57 310 555 1234" };
  assert.deepEqual(model.toPayload(form, user), {
    residuo: "reciclable",
    material: "Cartón. dos cajas",
    contacto: "3105551234",
    direccion: "Manzana 1, Casa 2",
    generador: "hogar",
    disponibilidad: "Sábado · Tarde (12:00 m. a 5:00 p. m.)",
    observaciones: "",
  });
  const other = { ...form, useOwnAddress: false, address: { ...addr.emptyAddress(), manzana: "7", casa: "9" } };
  assert.equal(model.toPayload(other, user).direccion, "Manzana 7, Casa 9, Villas de San Pablo, Barranquilla");
  assert.equal(model.toPayload(form, { profile: { ...user.profile, kind: "business" } }).generador, "unidad_productiva");
});

test("solicitud: cada paso valida lo suyo", () => {
  const user = { profile: { address: "x", phone: "3001234567", kind: "household" } };
  const form = model.emptyRequest(user);
  assert.ok(model.validateStep(0, form).material);
  assert.deepEqual(model.validateStep(0, { ...form, detail: "cáscaras" }), {});
  const step1 = model.validateStep(1, form);
  assert.ok(step1.days && step1.slots && !step1.contact);
  assert.ok(model.validateStep(1, { ...form, days: ["lun"], slots: ["tarde"], useOwnAddress: false }).manzana);
});

test("borrador: se recupera tras recargar y se descartan formas antiguas o corruptas", () => {
  globalThis.sessionStorage = memoryStorage();
  const draft = { key: "k1", step: 1, form: { residuo: "organico" } };
  model.writeDraft("d", draft);
  assert.deepEqual(model.readDraft("d"), draft);
  sessionStorage.setItem("d", JSON.stringify({ key: "k", data: {} }));
  assert.equal(model.readDraft("d"), null);
  sessionStorage.setItem("d", "{roto");
  assert.equal(model.readDraft("d"), null);
});
