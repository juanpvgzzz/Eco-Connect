"""Montaje desde la API común: app.include_router(router(service, authenticated_actor))."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.routing import APIRoute
from pydantic import Field

from .service import (
    Actor, Collections, Delivery, Direct, Input, Key, Problem, Reason, Record,
    Notice, Request, Schedule, State, Text, leader, local,
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


def router(service: Collections, authenticated_actor) -> APIRouter:
    routes = APIRouter(prefix="/recolecciones", route_class=OperationRoute)
    auth = Depends(authenticated_actor)

    @routes.post("", response_model=Record)
    def create(data: Request, key: Key = Header(alias="Idempotency-Key"), actor: Actor = auth):
        return service.create(actor, key, data)

    @routes.get("", response_model=list[Record])
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

    @routes.get("/{id}/historial")
    def history(id: UUID, actor: Actor = auth):
        with service.transaction() as tx:
            row = service.find(tx, actor, id)
            return tx.history(row.flujo, id)

    @routes.post("/{id}/programar", response_model=Record)
    def schedule(id: UUID, data: Schedule, actor: Actor = auth):
        return service.schedule(actor, id, data)

    @routes.post("/{id}/cancelar", response_model=Record)
    def cancel(id: UUID, data: Reason, actor: Actor = auth):
        return service.interrupt(actor, id, data, failed=False)

    @routes.post("/{id}/visita-fallida", response_model=Record)
    def failed(id: UUID, data: Reason, actor: Actor = auth):
        return service.interrupt(actor, id, data, failed=True)

    @routes.post("/{id}/cerrar", response_model=Record)
    def close(id: UUID, data: Delivery, actor: Actor = auth):
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
        leader(actor, garden_only=True)
        with service.transaction() as tx:
            return tx.set_stock(premio, data.cantidad, actor.id)

    @routes.post("/canjes/confirmar")
    def redeem(data: Redemption, actor: Actor = auth):
        leader(actor, garden_only=True)
        with service.transaction() as tx:
            return tx.redeem(data.codigo, actor.id)

    return routes
