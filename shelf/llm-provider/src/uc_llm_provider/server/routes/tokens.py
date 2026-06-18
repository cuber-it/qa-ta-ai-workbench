from fastapi import APIRouter, HTTPException

from ...core.base import EndpointNotAvailable
from ...core.models import TokenCountRequest
from ..registry import registry

router = APIRouter()


@router.post("/tokens/count")
async def count_tokens(request: TokenCountRequest):
    if registry.get() is None:
        raise HTTPException(status_code=503, detail={"error": {"message": "No provider"}})
    try:
        return await registry.get().count_tokens(request)
    except EndpointNotAvailable as e:
        raise HTTPException(status_code=501, detail={"error": {"message": e.detail.message}})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})
