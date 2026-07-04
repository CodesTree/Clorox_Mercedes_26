from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app import orm
from app.schemas import FaultOut

DEFAULT_SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "sample_odx"


class OdxFaultService:
    def __init__(self, sample_dir: Path = DEFAULT_SAMPLE_DIR):
        self.sample_dir = Path(sample_dir)

    def list_faults(self, session: Session | None = None) -> list[FaultOut]:
        if session is not None:
            cached = session.query(orm.DtcCode).order_by(orm.DtcCode.code).all()
            if cached:
                return [
                    FaultOut(
                        code=row.code,
                        description=row.description,
                        severity=row.severity,
                        system=row.system,
                    )
                    for row in cached
                ]

        faults = self._parse_sample_files()
        if session is not None and faults:
            for fault in faults:
                row = session.get(orm.DtcCode, fault.code)
                if row is None:
                    session.add(
                        orm.DtcCode(
                            code=fault.code,
                            description=fault.description,
                            severity=fault.severity,
                            system=fault.system,
                            source_odx=str(self.sample_dir),
                        )
                    )
                else:
                    row.description = fault.description
                    row.severity = fault.severity
                    row.system = fault.system
            session.commit()
        return faults

    def _parse_sample_files(self) -> list[FaultOut]:
        if not self.sample_dir.exists():
            return []

        files = sorted(self.sample_dir.glob("*.pdx")) + sorted(self.sample_dir.glob("*.odx*"))
        if not files:
            return []

        try:
            import odxtools
        except ImportError:
            return []

        faults: list[FaultOut] = []
        for file_path in files:
            try:
                db = odxtools.load_pdx_file(str(file_path)) if file_path.suffix == ".pdx" else odxtools.load_file(str(file_path))
            except Exception:
                continue
            faults.extend(_faults_from_diag_layers(getattr(db, "diag_layers", [])))
            if faults:
                break
        return faults


def _faults_from_diag_layers(diag_layers: Iterable[object]) -> list[FaultOut]:
    faults = _formal_dtc_faults(diag_layers)
    if faults:
        return faults
    return _fallback_diagnostic_faults(diag_layers)


def _formal_dtc_faults(diag_layers: Iterable[object]) -> list[FaultOut]:
    faults: list[FaultOut] = []
    for layer in diag_layers:
        spec = getattr(layer, "diag_data_dictionary_spec", None)
        dtc_dops = getattr(spec, "dtc_dops", []) if spec is not None else []
        for dop in dtc_dops or []:
            for dtc in getattr(dop, "dtcs", []) or []:
                code = str(getattr(dtc, "trouble_code", "") or getattr(dtc, "short_name", "")).strip()
                if not code:
                    continue
                description = str(
                    getattr(dtc, "display_trouble_code", "")
                    or getattr(dtc, "text", "")
                    or getattr(dtc, "short_name", code)
                )
                faults.append(
                    FaultOut(
                        code=code,
                        description=description,
                        severity="warn",
                        system=str(getattr(layer, "short_name", "diagnostics")),
                    )
                )
    return faults


def _fallback_diagnostic_faults(diag_layers: Iterable[object]) -> list[FaultOut]:
    for layer in diag_layers:
        for service in getattr(layer, "diag_comms", []) or []:
            if getattr(service, "short_name", "") != "report_status":
                continue
            response_names = [
                getattr(response, "short_name", "")
                for response in (getattr(service, "positive_responses", []) or [])
            ]
            description = "ODX diagnostic service exposes status data"
            if response_names:
                description = f"ODX diagnostic service exposes {', '.join(response_names)}"
            return [
                FaultOut(
                    code="ODX-REPORT-STATUS",
                    description=description,
                    severity="info",
                    system=str(getattr(layer, "short_name", "diagnostics")),
                )
            ]
    return []
