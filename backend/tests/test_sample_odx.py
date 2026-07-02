from pathlib import Path

import odxtools

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_odx" / "somersault.pdx"


def test_sample_pdx_exists_and_loads():
    assert SAMPLE.exists(), "generate it: see data/sample_odx/README.md"
    db = odxtools.load_pdx_file(str(SAMPLE))
    assert len(db.diag_layers) > 0
