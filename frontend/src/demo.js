const STORE = "eco.demo.v1";
const samples = [
  ["10001", "María Torres", "resident", null],
  ["20001", "Ana Pérez", "leader", "huerta"],
  ["30001", "Sara Díaz", "leader", "reciclaje"],
];
export const demoProfiles = [
  "Cliente",
  "Líder de huerta",
  "Líder de reciclaje",
].map((label, i) => ({
  label,
  national_id: samples[i][0],
  pin: "1234",
}));
const accounts = samples.map(
  ([national_id, full_name, role, collective_id], i) => ({
    id: "20000000-0000-4000-8000-00000000000" + (i + 1),
    collective_id,
    profile: {
      national_id,
      full_name,
      role,
      kind: "household",
      pilot_enabled: true,
      address: "Calle 12, Villas de San Pablo",
      phone: "3000000000",
    },
  }),
);
const workers = {
  huerta: ["30000000-0000-4000-8000-000000000001", "Luis Herrera"],
  reciclaje: ["30000000-0000-4000-8000-000000000002", "Rosa Mora"],
};
const statuses = {
  recibida: "received",
  programada: "scheduled",
  recolectada: "collected",
};
const titles = {
  recibida: "Solicitud recibida",
  programada: "Visita programada",
  reprogramada: "Cambio de cita",
  recolectada: "Recogida completada",
};

const registrationStore = "eco.demo.registrations.v1";
async function pinVerifier(pin, salt) {
  const bytes = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    bytes.encode(pin),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: bytes.encode(salt),
      iterations: 150000,
    },
    key,
    256,
  );
  return Array.from(new Uint8Array(bits), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}

async function serve(path, { token, body, key }) {
  const registrations = JSON.parse(
    localStorage.getItem(registrationStore) || "[]",
  );
  const identities = [...accounts, ...registrations.map((r) => r.identity)];
  if (path === "/accounts") {
    if (identities.some((a) => a.profile.national_id === body.national_id))
      throw Object.assign(Error("Esta cédula ya tiene una cuenta."), {
        status: 409,
      });
    const { pin, national_id, full_name, address, phone } = body;
    const identity = {
      id: crypto.randomUUID(),
      collective_id: null,
      profile: {
        national_id,
        full_name,
        address,
        phone,
        kind: "household",
        role: "resident",
        pilot_enabled: false,
      },
    };
    const salt = crypto.randomUUID();
    registrations.push({
      identity,
      salt,
      verifier: await pinVerifier(pin, salt),
    });
    localStorage.setItem(registrationStore, JSON.stringify(registrations));
    return identity;
  }
  if (path === "/accounts/login") {
    const account = identities.find(
      (a) => a.profile.national_id === body.national_id.replace(/[.\s-]/g, ""),
    );
    const registration = registrations.find(
      (r) => r.identity.id === account?.id,
    );
    const valid = registration
      ? (await pinVerifier(body.pin, registration.salt)) ===
        registration.verifier
      : body.pin === "1234";
    if (!account || !valid)
      throw Error("Revisa la cédula y el PIN de demostración.");
    return { access_token: "demo-" + account.id, token_type: "bearer" };
  }
  const user = identities.find((a) => "demo-" + a.id === token);
  if (!user)
    throw Object.assign(Error("Vuelve a iniciar sesión."), { status: 401 });
  if (path === "/accounts/me") return user;
  if (path === "/accounts/logout") return null;
  const db = JSON.parse(
    localStorage.getItem(STORE) || '{"rows":[],"events":[]}',
  );
  const own = db.rows.filter((r) => r.cliente === user.id);
  const leader = user.profile.role === "leader";
  const inbox = db.rows.filter((r) => leader && r.flujo === user.collective_id);
  const visible = leader ? inbox : own;
  const events = db.events.filter((e) =>
    visible.some((r) => r.id === e.solicitud_id),
  );
  function save(row, evento, motivo = null) {
    db.events.unshift({
      id: crypto.randomUUID(),
      solicitud_id: row.id,
      evento,
      cita: row.cita,
      responsable: row.responsable,
      motivo,
      created_at: new Date().toISOString(),
    });
    localStorage.setItem(STORE, JSON.stringify(db));
    return row;
  }
  if (path === "/community/points")
    return { balance: own.reduce((sum, r) => sum + (r.points || 0), 0) };
  if (path === "/community/appointments")
    return own
      .filter((r) => r.estado === "programada")
      .map((r) => ({
        collection_id: r.id,
        status: "scheduled",
        scheduled_at: r.cita,
        responsible_name: workers[r.flujo][1],
      }));
  if (path === "/community/collections")
    return own.map((r) => ({
      id: r.id,
      status: statuses[r.estado],
      description: r.solicitud.material,
      address: r.solicitud.direccion,
      created_at: r.created_at,
    }));
  if (path === "/community/notifications")
    return events.map((e) => ({
      id: e.id,
      title: titles[e.evento],
      message: own.find((r) => r.id === e.solicitud_id).solicitud.material,
      created_at: e.created_at,
    }));
  if (path === "/recolecciones/avisos") return events;
  if (path === "/recolecciones" && !body && leader) return inbox;
  if (path === "/recolecciones" && body && !leader && key) {
    if (!user.profile.pilot_enabled)
      throw Error(
        "Tu cuenta aún no está habilitada para recogidas del piloto.",
      );
    const existing = own.find((r) => r.key === key);
    if (existing) {
      if (JSON.stringify(existing.solicitud) !== JSON.stringify(body))
        throw Error("Esta clave ya corresponde a otra solicitud.");
      return existing;
    }
    const row = {
      id: crypto.randomUUID(),
      cliente: user.id,
      key,
      solicitud: body,
      flujo: body.residuo === "organico" ? "huerta" : "reciclaje",
      estado: "recibida",
      cita: null,
      responsable: null,
      programada_por: null,
      entrega: null,
      cerrada_por: null,
      created_at: new Date().toISOString(),
    };
    db.rows.unshift(row);
    return save(row, "recibida");
  }
  const [, , id, action] = path.split("/");
  const row = inbox.find((r) => r.id === id);
  if (
    row &&
    action === "programar" &&
    ["recibida", "programada"].includes(row.estado)
  ) {
    const again = row.estado === "programada";
    if (again && !body.motivo?.trim())
      throw Error("Indica el motivo del cambio.");
    Object.assign(row, {
      estado: "programada",
      cita: body.cita,
      responsable: workers[row.flujo][0],
      programada_por: user.id,
    });
    return save(row, again ? "reprogramada" : "programada", body.motivo);
  }
  if (row && action === "cerrar" && row.estado === "programada") {
    const points = Math.floor(Number(body.kilos) * 10);
    if (points < 1)
      throw Error(
        "Este peso no alcanza un punto con la tarifa de demostración.",
      );
    Object.assign(row, {
      estado: "recolectada",
      entrega: body,
      cerrada_por: user.id,
      points,
    });
    return save(row, "recolectada");
  }
  throw Error("Operación no disponible para este perfil o estado.");
}

export async function demoRequest(path, options) {
  return navigator.locks
    ? navigator.locks.request(STORE, () => serve(path, options))
    : serve(path, options);
}
