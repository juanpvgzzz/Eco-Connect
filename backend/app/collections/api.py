"""Montaje desde la API común: app.include_router(router(service, authenticated_actor))."""
from collections.abc import Mapping
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.routing import APIRoute
from pydantic import Field

from .service import (
    Actor, Collections, Delivery, Direct, Flow, InboxRecord, Input, Key, Member, MemberState, Notice, PickupResult, Problem, Reason, Record, Request, Schedule, State, Text, Week, WorkerNotice, leader, local,
)


class OperationRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def dispatch(request):
            try:
                return await handle(request)
            except Problem as error:
                raise HTTPException(error.status, detail=str(error)) from error

        return dispatch


class Stock(Input):
    cantidad: int = Field(ge=0, strict=True)


class Redemption(Input):
    codigo: Text


def account_actor(get_current_identity, collectives: Mapping[str, Flow]):
    """Adaptar la sesión de cuentas con el catálogo confiable de colectivos."""
    def authenticated(identity=Depends(get_current_identity)) -> Actor:
        role = identity.profile.role
        if role in ("resident", "business"):
            return Actor(UUID(identity.id), "cliente")
        flow = collectives.get(identity.collective_id)
        if role == "leader" and flow in ("huerta", "reciclaje"):
            return Actor(UUID(identity.id), "lider", flow)
        if role == "admin":
            return Actor(UUID(identity.id), "admin")
        if role == "field_worker" and flow in ("huerta", "reciclaje") and getattr(identity, "worker_id", None):
            return Actor(UUID(identity.id), "recolector", flow, trabajador_id=UUID(identity.worker_id))
        # Los recolectores son integrantes operativos sin acceso digital.
        raise HTTPException(403, detail="Perfil sin acceso a recolecciones")

    return authenticated


def router(service: Collections, authenticated_actor) -> APIRouter:
    routes = APIRouter(prefix="/recolecciones", route_class=OperationRoute)
    auth = Depends(authenticated_actor)

    @routes.post("", response_model=Record)
    def create(data: Request, key: Key = Header(alias="Idempotency-Key"), actor: Actor = auth):
        return service.create(actor, key, data)

    @routes.get("", response_model=list[InboxRecord])
    def inbox(estado: State | None = None, actor: Actor = auth):
        flow = leader(actor)
        with service.transaction() as tx:
            return tx.inbox(flow, estado)

    @routes.get("/avisos", response_model=list[Notice])
    def notices(actor: Actor = auth):
        with service.transaction() as tx:
            if actor.rol == "cliente":
                return tx.client_notices(actor.id)
            return tx.notices(leader(actor))

    @routes.get("/resumen")
    def summary(desde: datetime, hasta: datetime, actor: Actor = auth):
        flow = leader(actor)
        start, end = local(desde), local(hasta)
        if start >= end:
            raise Problem(422, "El fin del periodo debe ser posterior al inicio")
        with service.transaction() as tx:
            return tx.summary(flow, start, end)

    @routes.get("/recolectores")
    def workers(todos: bool = False, actor: Actor = auth):
        flow = leader(actor)
        with service.transaction() as tx:
            return tx.workers(flow, todos)

    @routes.post("/recolectores", status_code=201)
    def add_worker(data: Member, actor: Actor = auth):
        return service.add_member(actor, data)

    @routes.patch("/recolectores/{worker}")
    def set_worker(worker: UUID, data: MemberState, actor: Actor = auth):
        return service.set_member(actor, worker, data)

    @routes.get("/calendario", response_model=Week)
    def calendar(desde: date, flujo: Flow | None = None, actor: Actor = auth):
        return service.calendar(actor, desde, flujo)

    @routes.get("/materiales")
    def materials(actor: Actor = auth):
        if actor.rol == "recolector" and actor.flujo in ("huerta", "reciclaje"):
            pass
        else:
            leader(actor)
        with service.transaction() as tx:
            return tx.materials()

    @routes.get("/asignadas", response_model=list[InboxRecord])
    def assigned(actor: Actor = auth):
        # Recolector: únicamente sus recogidas asignadas (programadas y realizadas).
        if actor.rol != "recolector" or actor.trabajador_id is None or actor.flujo is None:
            raise Problem(403, "Se requiere un acceso operativo de recolector")
        with service.transaction() as tx:
            return tx.assigned(actor.trabajador_id, actor.flujo)

    @routes.get("/{id}/historial")
    def history(id: UUID, actor: Actor = auth):
        with service.transaction() as tx:
            if actor.rol == "recolector":
                row = tx.locked_assigned(actor.trabajador_id, actor.flujo, id) if actor.trabajador_id else None
                if row is None:
                    raise Problem(404, "Solicitud no asignada a este recolector")
            else:
                row = service.find(tx, actor, id)
            return tx.history(row.flujo, id)

    @routes.post("/{id}/programar", response_model=Record)
    def schedule(id: UUID, data: Schedule, actor: Actor = auth):
        return service.schedule(actor, id, data)

    @routes.post("/{id}/aviso-recolector", response_model=Record)
    def notify_worker(id: UUID, data: WorkerNotice, actor: Actor = auth):
        return service.notify_worker(actor, id, data)

    @routes.post("/{id}/revisar", response_model=Record)
    def review(id: UUID, actor: Actor = auth):
        return service.review(actor, id)

    @routes.post("/{id}/cancelar", response_model=Record)
    def cancel(id: UUID, data: Reason, actor: Actor = auth):
        return service.interrupt(actor, id, data, failed=False)

    @routes.post("/{id}/visita-fallida", response_model=Record)
    def failed(id: UUID, data: Reason, actor: Actor = auth):
        return service.interrupt(actor, id, data, failed=True)

    @routes.post("/{id}/cerrar", response_model=Record)
    def close(id: UUID, data: PickupResult, actor: Actor = auth):
        return service.close(actor, id, data)

    @routes.post("/directas", response_model=Record)
    def direct(data: Direct, actor: Actor = auth):
        return service.direct(actor, data)

    @routes.get("/existencias")
    def stock(actor: Actor = auth):
        leader(actor, garden_only=True)
        with service.transaction() as tx:
            return tx.stock()

    @routes.put("/existencias/{premio}")
    def update_stock(premio: UUID, data: Stock, actor: Actor = auth):
        if actor.rol != "admin":
            raise Problem(403, "Solo administración puede configurar existencias")
        with service.transaction() as tx:
            return tx.set_stock(premio, data.cantidad, actor.id)

    @routes.post("/canjes/confirmar")
    def redeem(data: Redemption, actor: Actor = auth):
        leader(actor, garden_only=True)
        with service.transaction() as tx:
            return tx.redeem(data.codigo, actor.id)

    return routes
