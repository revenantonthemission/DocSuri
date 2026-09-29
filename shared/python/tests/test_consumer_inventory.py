"""Consumer discovery must use the selected checkout and expose local wire candidates."""

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/inventory_consumers.py"


def test_inventory_resolves_selected_checkout_and_records_shadowing(tmp_path):
    shared = tmp_path / "shared/python/src/docsuri_shared"
    shared.mkdir(parents=True)
    (shared / "dtos.py").write_text("from ._generated.dtos.fixture import Wire as Public\n")
    backend = tmp_path / "backend"
    backend.mkdir()
    source = backend / "api.py"
    source.write_text("from docsuri_shared.dtos import Public as Local\nLocal = dict\n")
    inventory = runpy.run_path(str(SCRIPT))["inventory"]
    result = inventory(tmp_path)
    assert result["imports"][0]["generated"] == ["docsuri_shared._generated.dtos.fixture:Wire"]
    assert result["imports"][0]["shadowed"] is True


def test_local_pydantic_model_and_source_drift_are_visible(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    source = backend / "api.py"
    source.write_text(
        "from pydantic import BaseModel\nclass LocalResponse(BaseModel):\n    id: str\n"
    )
    inventory = runpy.run_path(str(SCRIPT))["inventory"]
    before = inventory(tmp_path)
    assert before["localModels"] == [{"file": "backend/api.py", "symbol": "LocalResponse",
                                      "bases": ["BaseModel"]}]
    source.write_text(source.read_text().replace("id: str", "id: int"))
    assert before["sourceDigests"] != inventory(tmp_path)["sourceDigests"]
