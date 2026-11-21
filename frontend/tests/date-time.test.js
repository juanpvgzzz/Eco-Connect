import { test } from "node:test";
import assert from "node:assert/strict";
import {
  bogotaDayKey, formatAvailability, formatDateTime, formatFullDate, formatMonth,
  formatShortDate, formatTime, toBogotaInput, toBogotaTimestamp,
} from "../src/utils/dateTime.js";

test("formatos es-CO para mañana, tarde y medianoche", () => {
  const morning = "2026-11-21T13:30:00Z";
  assert.equal(formatShortDate(morning), "21/11/2026");
  assert.equal(formatFullDate(morning), "sábado, 21 de noviembre de 2026");
  assert.equal(formatTime(morning), "8:30 a. m.");
  assert.equal(formatDateTime(morning), "21/11/2026, 8:30 a. m.");
  assert.equal(formatDateTime("2026-11-21T21:15:00Z"), "21/11/2026, 4:15 p. m.");
  assert.equal(formatTime("2026-11-21T05:00:00Z"), "12:00 a. m.");
});

test("una fecha civil conserva el día y no adquiere una hora", () => {
  assert.equal(bogotaDayKey("2026-12-01"), "2026-12-01");
  assert.equal(formatDateTime("2026-12-01"), "01/12/2026");
  assert.equal(formatTime("2026-12-01"), "");
  assert.equal(formatFullDate("2026-12-01"), "martes, 1 de diciembre de 2026");
});

test("un instante UTC puede pertenecer al día, mes o semana anterior de Colombia", () => {
  assert.equal(bogotaDayKey("2026-12-01T02:30:00Z"), "2026-11-30");
  assert.equal(formatMonth("2026-12-01T02:30:00Z"), "noviembre de 2026");
  assert.equal(bogotaDayKey("2026-11-23T04:59:00Z"), "2026-11-22");
  assert.equal(bogotaDayKey("2026-11-23T05:00:00Z"), "2026-11-23");
});

test("el valor del control de programación se recupera desde el equivalente UTC", () => {
  for (const [input, utc, label] of [
    ["2026-11-21T08:30", "2026-11-21T13:30:00.000Z", "21/11/2026, 8:30 a. m."],
    ["2026-11-30T22:30", "2026-12-01T03:30:00.000Z", "30/11/2026, 10:30 p. m."],
  ]) {
    const payload = toBogotaTimestamp(input);
    assert.equal(new Date(payload).toISOString(), utc);
    assert.equal(toBogotaInput(utc), input);
    assert.equal(formatDateTime(utc), label);
  }
});

test("disponibilidad con cambio de día y valores incompletos", () => {
  assert.equal(
    formatAvailability("2026-11-21T13:30:00Z/2026-11-21T16:00:00Z"),
    "sábado, 21 de noviembre de 2026, de 8:30 a. m. a 11:00 a. m.",
  );
  assert.equal(
    formatAvailability("2026-12-01T03:00:00Z/2026-12-01T05:30:00Z"),
    "30/11/2026, 10:00 p. m. – 01/12/2026, 12:30 a. m.",
  );
  assert.equal(formatAvailability("Lunes · Mañana"), "Lunes · Mañana");
  assert.equal(formatAvailability("2026-11-30/2026-12-01"), "30/11/2026 – 01/12/2026");
  for (const missing of [undefined, null, "", "no es una fecha", "2026-02-30", "2026-13-01T08:30:00Z"]) {
    assert.equal(formatDateTime(missing), "");
    assert.equal(bogotaDayKey(missing), "");
  }
  assert.equal(toBogotaTimestamp("2026-11-21T24:30"), "");
});
