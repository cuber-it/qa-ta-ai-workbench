from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..registry import registry

router = APIRouter()


class ProviderSwapRequest(BaseModel):
    provider_type: str
    model:         str  | None = None
    api_key:       str  | None = None
    api_base:      str  | None = None


@router.get("/provider")
def get_provider_info():
    return registry.info()


@router.put("/provider")
async def swap_provider(req: ProviderSwapRequest):
    config = {"name": req.provider_type, "provider_type": req.provider_type}
    if req.model:
        config["default_model"] = req.model
    if req.api_key:
        config["api_key"] = req.api_key
    if req.api_base:
        config["api_base"] = req.api_base
    try:
        await registry.swap(config)
        return registry.info()
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": {"message": str(e)}})
