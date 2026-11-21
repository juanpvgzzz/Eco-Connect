import { after, test } from "node:test";
import assert from "node:assert/strict";
import { close, load, memoryStorage } from "./helpers.js";

after(close);

test("demo: se puede iniciar sesión y cargar los tres paneles de prueba", async (context) => {
  process.env.VITE_DEMO_MODE = "true";
  globalThis.localStorage = memoryStorage();
  globalThis.sessionStorage = memoryStorage();
  context.mock.method(globalThis, "fetch", () => assert.fail("La demo no debe consultar FastAPI"));

  const { request, isDemo } = await load("/src/services/api.js");
  const { demoProfiles } = await load("/src/demo.js");
  const { restoreSession } = await load("/src/app/App.jsx");
  assert.equal(isDemo, true);

  const workersByFlow = new Map();
  for (const { label, national_id, pin } of demoProfiles) {
    const { access_token } = await request("/accounts/login", { body: { national_id, pin } });
    const { user, token } = await restoreSession(access_token);
    assert.equal(user.profile.national_id, national_id, label);

    if (user.profile.role === "resident") {
      const [rows, notices, appointments, points] = await Promise.all([
        "/community/collections", "/community/notifications", "/community/appointments", "/community/points",
      ].map((path) => request(path, { token })));
      assert.deepEqual([rows, notices, appointments, points.balance], [[], [], [], 0]);
      const participation = await request("/community/points/participation", { token });
      assert.equal(participation.completed, 0);
      assert.deepEqual(participation.milestones.map((item) => item.pickups), [1, 3, 5, 10, 20]);
      assert.ok(participation.milestones.every((item) => item.unlocked_at === null));
      assert.deepEqual(await request("/community/rewards", { token }), []);
      await assert.rejects(request("/recolecciones/recolectores", { token }));
    } else {
      assert.equal(user.profile.role, "leader", label);
      const [rows, notices, workers, materials] = await Promise.all([
        "/recolecciones", "/recolecciones/avisos", "/recolecciones/recolectores", "/recolecciones/materiales",
      ].map((path) => request(path, { token })));
      assert.deepEqual([rows, notices], [[], []]);
      assert.equal(workers.length, 1);
      assert.ok(workers[0].active);
      assert.ok(materials.every(({ code, name }) => code && name));
      assert.ok(materials.length > 0);
      assert.deepEqual(await request("/recolecciones/recolectores?todos=true", { token }), workers);
      workersByFlow.set(user.collective_flow, workers[0].id);
    }
  }

  assert.deepEqual([...workersByFlow.keys()].sort(), ["huerta", "reciclaje"]);
  assert.notEqual(workersByFlow.get("huerta"), workersByFlow.get("reciclaje"));
});
