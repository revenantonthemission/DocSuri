"""An earlier assembly's profile on the shared host's liveness route (U8 plan Step 40).

U8 names the profile kind on `/health/live` (your decision of 2026-10-24). An earlier
unit may build its profile without `is_production` (U5's real composition test builds a
`SimpleNamespace`), and must keep its built answer, `synthetic-local`.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.local_host import assemble


def live(profile) -> dict:
    with TestClient(assemble(profile), base_url="https://127.0.0.1") as client:
        answer = client.get("/health/live")
    assert answer.status_code == 200
    return answer.json()


def test_a_profile_without_the_flag_keeps_the_built_answer():
    profile = SimpleNamespace(origin="https://127.0.0.1:18089")
    assert not hasattr(profile, "is_production")
    assert live(profile) == {"process": "alive", "profile": "synthetic-local"}


def test_a_profile_with_the_flag_off_keeps_the_built_answer():
    profile = SimpleNamespace(origin="https://127.0.0.1:18089", is_production=False)
    assert live(profile) == {"process": "alive", "profile": "synthetic-local"}


def test_a_profile_with_the_flag_on_names_production():
    profile = SimpleNamespace(origin="https://127.0.0.1:18089", is_production=True)
    assert live(profile)["profile"] == "production"
