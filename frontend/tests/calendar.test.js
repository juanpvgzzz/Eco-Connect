// Calendario semanal: aritmética de semanas con fechas civiles y hora de Bogotá.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { close, load } from "./helpers.js";

let w;
before(async () => {
  w = await load("/src/features/calendar/week.js");
});
after(close);

test("lunes de la semana para cualquier día, incluido el domingo", () => {
  assert.equal(w.mondayOf("2026-11-25"), "2026-11-23"); // miércoles
  assert.equal(w.mondayOf("2026-11-29"), "2026-11-23"); // domingo
  assert.equal(w.mondayOf("2026-11-23"), "2026-11-23"); // lunes
});

test("cambio de semana entre meses y años", () => {
  assert.equal(w.addDays("2026-11-30", 7), "2026-12-07");
  assert.equal(w.addDays("2026-12-28", 7), "2027-01-04");
  assert.equal(w.addDays("2027-01-04", -7), "2026-12-28");
  assert.deepEqual(w.weekDays("2026-12-28"), ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"]);
  assert.equal(w.mondayOf("2028-03-01"), "2028-02-28"); // año bisiesto
});

test("rótulos de rango y días en español", () => {
  assert.equal(w.rangeLabel("2026-11-23"), "23 de noviembre – 29 de noviembre de 2026");
  assert.equal(w.rangeLabel("2026-12-28"), "28 de diciembre de 2026 – 3 de enero de 2027");
  assert.equal(w.dayName("2026-11-23"), "Lunes");
});

test("la hora se calcula en America/Bogota, no en UTC", () => {
  // Domingo 23:30 en Bogotá = lunes 04:30 UTC: debe contar como las 23 h.
  assert.equal(w.bogotaHour("2026-11-30T04:30:00Z"), 23);
  assert.equal(w.bogotaHour("2026-11-25T09:30:00-05:00"), 9);
});
