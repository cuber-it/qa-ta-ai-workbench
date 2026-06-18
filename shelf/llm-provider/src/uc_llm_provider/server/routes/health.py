import time

from fastapi import APIRouter, HTTPException

from ..registry import registry

router = APIRouter()


def _check():
    if registry.get() is None:
        raise HTTPException(status_code=503, detail={"error": {"message": "No provider configured"}})


@router.get("/health")
def health():
    p = registry.get()
    if p is None:
        return {"status": "no_provider"}
    h = p.health()
    return {"status": h.status, "provider": h.provider, "model": p.get_default_model(), "timestamp": h.timestamp}


@router.get("/capabilities")
def capabilities():
    _check()
    caps = registry.get().get_capabilities()
    return {"provider": caps.provider, "tier1": caps.tiers.core,
            "tier2": caps.tiers.extended, "tier3": caps.tiers.specialized,
            "features": caps.features}


@router.get("/models")
def list_models():
    _check()
    p = registry.get()
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "created": int(time.time()), "owned_by": p.provider_name}
            for m in p.get_models()
        ],
    }


@router.get("/models/{model_id}")
async def model_detail(model_id: str):
    _check()
    try:
        d = await registry.get().get_model_detail(model_id)
        return {"id": d.id, "object": "model", "owned_by": d.owned_by or registry.get().provider_name}
    except Exception as e:
        raise HTTPException(status_code=404, detail={"error": {"message": str(e)}})
