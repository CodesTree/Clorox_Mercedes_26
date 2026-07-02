from fastapi import APIRouter, HTTPException

from app.schemas import ObdSnapshotOut

router = APIRouter(tags=["telemetry"])

_NOT_IMPLEMENTED = "Not implemented in foundation - Phase 03 provides the simulated OBD-II service."


@router.get("/obd/snapshot", response_model=ObdSnapshotOut)
def obd_snapshot(profile_id: int) -> ObdSnapshotOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)


@router.get("/obd/stream")
def obd_stream(profile_id: int):
    """SSE stream of ObdSnapshotOut payloads (implemented in Phase 03)."""
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)
