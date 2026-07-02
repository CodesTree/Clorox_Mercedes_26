# Sample ODX data

`somersault.pdx` is the official example ECU dataset from
[mercedes-benz/odxtools](https://github.com/mercedes-benz/odxtools), generated with
`examples/mksomersaultpdx.py` at the version pinned in `backend/requirements.txt`.

It is real ODX example data (not hand-authored) and is what Phase 03's `/odx/faults`
parses via `odxtools.load_pdx_file`. Regenerate with the same script if the odxtools
pin changes.
