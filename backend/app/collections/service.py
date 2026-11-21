"""Operaciones de recolección. El adaptador PostgreSQL proporciona una transacción por llamada."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Callable, ContextManager, Literal, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Flow = Literal["huerta", "reciclaje"]
State = Literal["recibida", "revision", "programada", "recolectada", "cancelada"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Weight = Annotated[Decimal, Field(gt=0, le=10000, max_digits=12, decimal_places=3)]
BARRANQUILLA = ZoneInfo("America/Bogota")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Request(Input):
    residuo: Literal["organico", "reciclable"]
    material: Text
    contacto: Text
    direccion: Text
    generador: Literal["hogar", "unidad_productiva"]
    disponibilidad: Text
    observaciones: str = Field(default="", max_length=2000)


class Schedule(Input):
    """Programación manual: fecha, hora y recolector elegido por la coordinadora."""
    cita: datetime
    responsable: UUID
    motivo: Text | None = None

    @field_validator("cita", mode="before")
    @classmethod
    def requires_time(cls, value):
        # Una fecha sin hora («2026-12-01») no basta para programar una visita.
        if isinstance(value, str) and "T" not in value.upper() and " " not in value.strip():
            raise ValueError("Indique la fecha y la hora de la visita")
        return value

    @field_validator("cita")
    @classmethod
    def in_the_future(cls, value: datetime) -> datetime:
        # Hora de Colombia (America/Bogota, UTC−5 sin horario de verano). Rechaza
        # también horas ya pasadas del día actual.
        if local(value) <= datetime.now(BARRANQUILLA):
            raise ValueError("La cita debe ser posterior a la fecha y hora actuales")
        return value


class Member(Input):
    """Integrante operativo de un colectivo (registro sin cuenta de usuario)."""
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class MemberState(Input):
    activo: bool


class WorkerNotice(Input):
    """Registro de que la coordinadora avisó al recolector (no envía mensajes)."""
    canal: Literal["llamada", "whatsapp", "mensaje", "en_persona"]
    nota: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class Reason(Input):
    motivo: Text


class Delivery(Input):
    material: Text
    kilos: Weight
    resultado: Literal["total", "parcial"]


class Outcome(Delivery):
    """Resultado guardado. Los campos de trazabilidad son opcionales para leer
    entregas directas y cierres anteriores a la fase 3."""
    unidad: Literal["kg"] = "kg"  # unidad de la cantidad entregada (base del cálculo de puntos)
    recogida_en: datetime | None = None
    recolector: UUID | None = None
    constancia: Text | None = None
    observaciones: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class PickupResult(Outcome):
    """Registro de una recogida programada. Lo hace el recolector asignado desde su
    acceso operativo, o la coordinadora con la constancia de lo que él le informó."""
    recogida_en: datetime

    @field_validator("recogida_en")
    @classmethod
    def already_happened(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=BARRANQUILLA)
        value = value.astimezone(BARRANQUILLA)
        if value > datetime.now(BARRANQUILLA) + timedelta(minutes=5):
            raise ValueError("La fecha real de recogida no puede estar en el futuro")
        return value


class Direct(Delivery):
    cliente: UUID
    clave: Key


@dataclass(frozen=True)
class Actor:
    id: UUID
    rol: str
    flujo: Flow | None = None
    generador: Literal["hogar", "unidad_productiva"] | None = None
    trabajador_id: UUID | None = None  # recolector: integrante operativo vinculado


class Record(BaseModel):
    id: UUID
    cliente: UUID
    flujo: Flow
    estado: State = "recibida"
    solicitud: Request | None = None
    cita: datetime | None = None
    responsable: UUID | None = None
    programada_por: UUID | None = None
    entrega: Outcome | None = None
    cerrada_por: UUID | None = None


class InboxRecord(Record):
    """Fila de la bandeja con el nombre del responsable para mostrarlo en pantalla."""

    nombre_responsable: str | None = None


class CalendarItem(InboxRecord):
    """Recogida en el calendario: `creada` (alta de la solicitud) es distinta de `cita`."""
    creada: datetime | None = None
    material: str | None = None  # resumen sin datos personales (vista de administración)


class Week(BaseModel):
    desde: date
    hasta: date
    programadas: list[CalendarItem]
    pendientes: list[CalendarItem]


class Notice(BaseModel):
    solicitud_id: UUID
    evento: str
    cita: datetime | None = None
    responsable: UUID | None = None
    motivo: str | None = None


class Transaction(Protocol):
    def pilot(self, client: UUID) -> bool: ...
    def reserve(self, scope: str, owner: UUID, key: str, new: Record) -> tuple[Record, bool]:
        """Insertar o devolver fila existente bloqueada, unicidad por (scope, owner, key)."""
        ...
    def locked(self, flow: Flow, id: UUID) -> Record | None: ...
    def workers(self, flow: Flow, include_inactive: bool = False) -> list[dict]: ...
    def add_worker(self, flow: Flow, name: str) -> dict: ...
    def set_worker_active(self, flow: Flow, worker: UUID, active: bool) -> dict | None: ...
    def materials(self) -> list[dict]: ...
    def worker_in_flow(self, flow: Flow, worker: UUID) -> bool: ...
    def save(self, row: Record) -> None: ...
    def on_duty(self, flow: Flow, at: datetime) -> UUID | None: ...
    def event(self, row: Record, kind: str, author: UUID, reason: str | None) -> None:
        """Persistir instantánea de historial y avisos para colectivo y cliente en la misma transacción."""
        ...
    def credit(self, delivery_id: UUID, client: UUID, material: str, kilos: Decimal) -> None: ...
    def inbox(self, flow: Flow, state: State | None) -> list[Record]: ...
    def scheduled_between(self, flows: tuple[Flow, ...], start: datetime, end: datetime) -> list[CalendarItem]: ...
    def locked_assigned(self, worker: UUID, flow: Flow, id: UUID) -> Record | None: ...
    def assigned(self, worker: UUID, flow: Flow) -> list[Record]: ...
    def unscheduled(self, flows: tuple[Flow, ...]) -> list[CalendarItem]: ...
    def notices(self, flow: Flow) -> list[Notice]: ...
    def client_notices(self, client: UUID) -> list[Notice]: ...
    def history(self, flow: Flow, id: UUID) -> list[dict]: ...
    def summary(self, flow: Flow, start: datetime, end: datetime) -> dict: ...
    def stock(self) -> list[dict]: ...
    def set_stock(self, reward: UUID, quantity: int, author: UUID) -> dict: ...
    def redeem(self, code: str, author: UUID) -> dict:
        """Confirmación idempotente con consumo, débito y stock atómicos."""
        ...


class Problem(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def leader(actor: Actor, garden_only=False) -> Flow:
    if actor.rol != "lider" or actor.flujo not in ("huerta", "reciclaje"):
        raise Problem(403, "Se requiere liderazgo del colectivo")
    if garden_only and actor.flujo != "huerta":
        raise Problem(403, "Se requiere liderazgo de huerta")
    return actor.flujo


def local(at: datetime) -> datetime:
    if at.tzinfo is None:
        return at.replace(tzinfo=BARRANQUILLA)
    return at.astimezone(BARRANQUILLA)


class Collections:
    def __init__(self, transaction: Callable[[], ContextManager[Transaction]]):
        self.transaction = transaction

    def calendar(self, actor: Actor, start: date, flow: Flow | None = None) -> Week:
        """Semana operativa (lunes a domingo, hora de Bogotá) filtrada en PostgreSQL.
        Coordinadora: solo su colectivo. Administración: ambos o el elegido."""
        if actor.rol == "lider":
            own = leader(actor)
            if flow is not None and flow != own:
                raise Problem(403, "Solo puede consultar el calendario de su colectivo")
            flows = (own,)
        elif actor.rol == "admin":
            flows = (flow,) if flow else ("huerta", "reciclaje")
        else:
            raise Problem(403, "Se requiere coordinación o administración")
        if start.weekday() != 0:
            raise Problem(422, "La semana debe empezar en lunes")
        begin = datetime.combine(start, time(0), BARRANQUILLA)
        with self.transaction() as tx:
            week = Week(
                desde=start, hasta=start + timedelta(days=6),
                programadas=tx.scheduled_between(flows, begin, begin + timedelta(days=7)),
                pendientes=tx.unscheduled(flows),
            )
        if actor.rol == "admin":
            # RN-07: administración no atiende solicitudes; no ve contacto ni dirección.
            redact = lambda items: [i.model_copy(update={"solicitud": None, "material": i.solicitud.material if i.solicitud else None})
                                    for i in items]
            week = week.model_copy(update={"programadas": redact(week.programadas), "pendientes": redact(week.pendientes)})
        return week

    def create(self, actor: Actor, key: str, request: Request) -> Record:
        if actor.rol != "cliente":
            raise Problem(403, "Se requiere perfil de cliente")
        key = key.strip()
        if not 1 <= len(key) <= 128:
            raise Problem(422, "Clave de reintento inválida")
        if actor.generador is not None:
            request = request.model_copy(update={"generador": actor.generador})
        flow = "huerta" if request.residuo == "organico" else "reciclaje"
        with self.transaction() as tx:
            self.require_pilot(tx, actor.id)
            new = Record(id=uuid4(), cliente=actor.id, flujo=flow, solicitud=request)
            row, created = tx.reserve("solicitud", actor.id, key, new)
            if row.solicitud != request:
                raise Problem(409, "Clave utilizada con otros datos")
            if created:
                tx.event(row, "recibida", actor.id, None)
            return row

    @staticmethod
    def require_pilot(tx, client):
        if not tx.pilot(client):
            raise Problem(403, "Cliente fuera del piloto")

    @staticmethod
    def find(tx, actor, id):
        row = tx.locked(leader(actor), id)
        if row is None:
            raise Problem(404, "Solicitud desconocida")
        return row

    def schedule(self, actor: Actor, id: UUID, data: Schedule):
        at = local(data.cita)
        with self.transaction() as tx:
            row = self.find(tx, actor, id)
            if row.estado not in ("recibida", "revision", "programada"):
                raise Problem(409, "Solicitud finalizada")
            again = row.estado == "programada"
            if again and not data.motivo:
                raise Problem(422, "Indique el motivo de reprogramación")
            # Asignación manual: el recolector debe ser un integrante activo del
            # mismo colectivo. Nunca queda «programada» sin fecha, hora y responsable.
            worker = data.responsable
            if not tx.worker_in_flow(row.flujo, worker):
                raise Problem(422, "El recolector no pertenece a este colectivo o está inactivo")
            row.cita, row.responsable, row.programada_por = at, worker, actor.id
            row.estado = "programada"
            tx.save(row)
            tx.event(row, "reprogramada" if again else "programada", actor.id, data.motivo)
            return row

    def add_member(self, actor: Actor, data: Member) -> dict:
        flow = leader(actor)
        with self.transaction() as tx:
            return tx.add_worker(flow, data.nombre)

    def set_member(self, actor: Actor, worker: UUID, data: MemberState) -> dict:
        flow = leader(actor)
        with self.transaction() as tx:
            member = tx.set_worker_active(flow, worker, data.activo)
            if member is None:
                raise Problem(404, "Integrante desconocido")
            return member

    def notify_worker(self, actor: Actor, id: UUID, data: WorkerNotice):
        labels = {"llamada": "Llamada", "whatsapp": "WhatsApp", "mensaje": "Mensaje de texto", "en_persona": "En persona"}
        with self.transaction() as tx:
            row = self.find(tx, actor, id)
            if row.estado != "programada" or row.responsable is None:
                raise Problem(409, "Solo se registra el aviso de recogidas programadas")
            reason = labels[data.canal] + (f": {data.nota}" if data.nota else "")
            tx.event(row, "aviso_recolector", actor.id, reason)
            return row

    def review(self, actor: Actor, id: UUID):
        with self.transaction() as tx:
            row = self.find(tx, actor, id)
            if row.estado != "recibida":
                raise Problem(409, "Solo se pueden revisar solicitudes recibidas")
            row.estado = "revision"
            tx.save(row)
            tx.event(row, "revision", actor.id, None)
            return row

    def interrupt(self, actor: Actor, id: UUID, reason: Reason, *, failed: bool):
        with self.transaction() as tx:
            row = self.find(tx, actor, id)
            if row.estado not in ("recibida", "revision", "programada") or (failed and row.estado != "programada"):
                raise Problem(409, "Estado incompatible con la operación")
            row.estado = "recibida" if failed else "cancelada"
            # El historial conserva el turno de la visita antes de liberar la cita.
            tx.event(row, "visita_fallida" if failed else "cancelada", actor.id, reason.motivo)
            row.cita = row.responsable = row.programada_por = None
            tx.save(row)
            return row

    @staticmethod
    def finish(tx, row, actor, delivery, kind):
        row.estado, row.entrega, row.cerrada_por = "recolectada", delivery, actor.id
        tx.save(row)
        tx.credit(row.id, row.cliente, delivery.material, delivery.kilos)
        tx.event(row, kind, actor.id, None)
        return row

    def close(self, actor: Actor, id: UUID, delivery: PickupResult):
        with self.transaction() as tx:
            if actor.rol == "recolector":
                # Solo su propia asignación; queda registrado como autor de la operación.
                if actor.trabajador_id is None or actor.flujo is None:
                    raise Problem(403, "Cuenta de recolector no vinculada")
                row = tx.locked_assigned(actor.trabajador_id, actor.flujo, id)
                if row is None:
                    raise Problem(404, "Solicitud no asignada a este recolector")
                delivery = delivery.model_copy(update={"recolector": actor.trabajador_id})
            else:
                row = self.find(tx, actor, id)  # coordinadora del mismo colectivo
                if delivery.recolector is None:
                    delivery = delivery.model_copy(update={"recolector": row.responsable})
                if not delivery.constancia:
                    raise Problem(422, "Indique cómo le informó el recolector el resultado")
            same = lambda: row.entrega and row.entrega.model_dump(mode="json") == delivery.model_dump(mode="json")
            if row.estado == "recolectada":
                if same():
                    return row  # reintento idéntico: no duplica entrega ni puntos
                raise Problem(409, "La recogida ya tiene un resultado registrado")
            if row.estado != "programada":
                raise Problem(409, "Se requiere una solicitud programada")
            if not tx.worker_in_flow(row.flujo, delivery.recolector):
                raise Problem(422, "El recolector no pertenece a este colectivo o está inactivo")
            return self.finish(tx, row, actor, delivery, "recolectada")

    def direct(self, actor: Actor, data: Direct):
        flow = leader(actor, garden_only=True)
        delivery = Outcome(**data.model_dump(exclude={"cliente", "clave"}))
        with self.transaction() as tx:
            self.require_pilot(tx, data.cliente)
            new = Record(id=uuid4(), cliente=data.cliente, flujo=flow)
            row, created = tx.reserve("directa", actor.id, data.clave, new)
            if created:
                return self.finish(tx, row, actor, delivery, "entrega_directa")
            # Comparar solo los campos de la entrega: lo leído de la base trae
            # además los campos opcionales de trazabilidad en None.
            fields = set(Delivery.model_fields)
            same = row.entrega and row.entrega.model_dump(mode="json", include=fields) == delivery.model_dump(mode="json", include=fields)
            if row.cliente != data.cliente or not same:
                raise Problem(409, "Clave utilizada con otros datos")
            return row
