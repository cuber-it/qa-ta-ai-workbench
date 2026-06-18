from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...core.base import EndpointNotAvailable
from ...core.models import ChatRequest, ErrorEvent
from ..registry import registry

router = APIRouter()


def _check():
    if registry.get() is None:
        raise HTTPException(status_code=503, detail={"error": {"message": "No provider configured"}})


@router.post("/chat")
async def chat(request: ChatRequest):
    _check()
    try:
        if request.stream:
            return StreamingResponse(_stream(request), media_type="text/event-stream")
        resp = await registry.get().chat(request)
        return resp
    except EndpointNotAvailable as e:
        raise HTTPException(status_code=501, detail={"error": {"message": e.detail.message}})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})


async def _stream(request: ChatRequest):
    try:
        async for event in registry.get().chat_stream(request):
            yield f"data: {event.model_dump_json(exclude_none=True)}\n\n"
    except Exception as e:
        err = ErrorEvent(message=str(e))
        yield f"data: {err.model_dump_json()}\n\n"
    yield "data: [DONE]\n\n"
