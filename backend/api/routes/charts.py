"""REST API per il recupero e la gestione dei grafici generati dall'agente."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/charts", tags=["charts"])


def _get_store(request: Request):
    """Recupera il ChartStore dal plugin chart_generator tramite AppContext."""
    ctx = request.app.state.context
    if ctx.plugin_manager is None:
        raise HTTPException(
            status_code=503, detail="Plugin manager not available",
        )
    plugin = ctx.plugin_manager.get_plugin("chart_generator")
    if plugin is None or not ctx.config.chart.enabled:
        raise HTTPException(status_code=503, detail="Plugin chart_generator non disponibile.")
    store = plugin.store
    if store is None:
        raise HTTPException(status_code=503, detail="ChartStore non inizializzato.")
    return store


@router.get("/{chart_id}", summary="Recupera la spec completa di un grafico")
async def get_chart(chart_id: str, request: Request) -> JSONResponse:
    """Restituisce il JSON completo della ChartSpec (inclusa echarts_option)."""
    store = _get_store(request)
    try:
        spec = await store.load(chart_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Grafico non trovato: {chart_id}")
    return JSONResponse(content=spec.model_dump(mode="json"))


@router.get("", summary="Lista grafici salvati")
async def list_charts(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Restituisce la lista paginata dei grafici, ordinata dal più recente."""
    store = _get_store(request)
    items = await store.list(limit=min(limit, 100), offset=offset)
    total = await store.count()
    return {
        "charts": [item.model_dump(mode="json") for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/{chart_id}", summary="Elimina un grafico")
async def delete_chart(chart_id: str, request: Request) -> dict[str, str]:
    """Elimina il file JSON del grafico dal disco."""
    store = _get_store(request)
    try:
        deleted = await store.delete(chart_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Grafico non trovato: {chart_id}")
    return {"status": "deleted", "chart_id": chart_id}
