"""Operaciones de recolección. El adaptador PostgreSQL proporciona una transacción por llamada."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Callable, ContextManager, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Flow = Literal["huerta", "reciclaje"]
State = Literal["recibida", "programada", "recolectada", "cancelada"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Weight = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
BARRANQUILLA = timezone(timedelta(hours=-5))


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
    cita: datetime
    motivo: Text | None = None


class Reason(Input):
    motivo: Text


class Delivery(Input):
    material: Text
    kilos: Weight
    resultado: Literal["total", "parcial"]


class Direct(Delivery):
    cliente: UUID
    clave: Key


@dataclass(frozen=True)
class Actor:
    id: UUID
    rol: str
    flujo: Flow | None = None


class Record(BaseModel):
    id: UUID
    cliente: UUID
    flujo: Flow
    estado: State = "recibida"
    solicitud: Request | None = None
    cita: datetime | None = None
    responsable: UUID | None = None
    programada_por: UUID | None = None
    entrega: Delivery | None = None
    cerrada_por: UUID | None = None


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
    def save(self, row: Record) -> None: ...
    def on_duty(self, flow: Flow, at: datetime) -> UUID | None: ...
    def event(self, row: Record, kind: str, author: UUID, reason: str | None) -> None:
        """Persistir instantánea de historial y avisos para colectivo y cliente en la misma transacción."""
        ...
    def credit(self, delivery_id: UUID, client: UUID, material: str, kilos: Decimal) -> None: ...
    def inbox(self, flow: Flow, state: State | None) -> list[Record]: ...
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

    def create(self, actor: Actor, key: str, request: Request) -> Record:
        if actor.rol != "cliente":
            raise Problem(403, "Se requiere perfil de cliente")
        key = key.strip()
        if not 1 <= len(key) <= 128:
            raise Problem(422, "Clave de reintento inválida")
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
            if row.estado not in ("recibida", "programada"):
                raise Problem(409, "Solicitud finalizada")
            again = row.estado == "programada"
            if again and not data.motivo:
                raise Problem(422, "Indique el motivo de reprogramación")
            worker = tx.on_duty(row.flujo, at)
            if worker is None:
                raise Problem(409, "Sin responsable de turno para esa cita")
            row.cita, row.responsable, row.programada_por = at, worker, actor.id
            row.estado = "programada"
            tx.save(row)
            tx.event(row, "reprogramada" if again else "programada", actor.id, data.motivo)
            return row

    def interrupt(self, actor: Actor, id: UUID, reason: Reason, *, failed: bool):
        with self.transaction() as tx:
            row = self.find(tx, actor, id)
            if row.estado not in ("recibida", "programada") or (failed and row.estado != "programada"):
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
        tx.event(row, kind, actor.id, None)
        tx.credit(row.id, row.cliente, delivery.material, delivery.kilos)
        return row

    def close(self, actor: Actor, id: UUID, delivery: Delivery):
        with self.transaction() as tx:
            row = self.find(tx, actor, id)
            if row.estado == "recolectada" and row.entrega == delivery:
                return row
            if row.estado != "programada":
                raise Problem(409, "Se requiere una solicitud programada")
            return self.finish(tx, row, actor, delivery, "recolectada")

    def direct(self, actor: Actor, data: Direct):
        flow = leader(actor, garden_only=True)
        delivery = Delivery(**data.model_dump(exclude={"cliente", "clave"}))
        with self.transaction() as tx:
            self.require_pilot(tx, data.cliente)
            new = Record(id=uuid4(), cliente=data.cliente, flujo=flow)
            row, created = tx.reserve("directa", actor.id, data.clave, new)
            if created:
                return self.finish(tx, row, actor, delivery, "entrega_directa")
            if row.cliente != data.cliente or row.entrega != delivery:
                raise Problem(409, "Clave utilizada con otros datos")
            return row
