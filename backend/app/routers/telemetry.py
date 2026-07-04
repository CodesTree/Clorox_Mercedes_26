import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas import ObdSnapshotOut
from app.db import get_session
from app.services.obd_sim import ObdSimulator
from app.services.odx_service import OdxFaultService
from app.services.vehicle import ProfileNotFound, get_profile

router = APIRouter(tags=["telemetry"])

obd_simulator = ObdSimulator()
odx_service = OdxFaultService()


@router.get("/obd/snapshot", response_model=ObdSnapshotOut)
def obd_snapshot(
    profile_id: int,
    session: Session = Depends(get_session),
) -> ObdSnapshotOut:
    try:
        profile = get_profile(session, profile_id)
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    fault_count = len(odx_service.list_faults(session))
    return obd_simulator.snapshot(profile=profile, fault_count=fault_count)


@router.get("/obd/stream")
def obd_stream(
    profile_id: int,
    max_events: int = Query(default=20, ge=1, le=100),
    interval_seconds: float = Query(default=1.0, ge=0.0, le=30.0),
    session: Session = Depends(get_session),
):
    try:
        profile = get_profile(session, profile_id)
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    fault_count = len(odx_service.list_faults(session))

    async def events():
        for index in range(max_events):
            snapshot = obd_simulator.snapshot(profile=profile, fault_count=fault_count)
            yield f"event: snapshot\ndata: {snapshot.model_dump_json()}\n\n"
            if index < max_events - 1 and interval_seconds > 0:
                await asyncio.sleep(interval_seconds)

    return StreamingResponse(events(), media_type="text/event-stream")
