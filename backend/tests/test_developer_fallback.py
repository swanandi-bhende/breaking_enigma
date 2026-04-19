from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agents.developer import DeveloperAgent, _fallback_plan, run_developer_agent


class _DumpableModel:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, mode: str = "json"):
        return self._payload


def _build_input(run_id: uuid.UUID | None = None):
    actual_run_id = run_id or uuid.uuid4()
    prd = _DumpableModel(
        {
            "product_vision": {"elevator_pitch": "Fallback product"},
            "user_stories": [],
            "features": {},
        }
    )
    design_spec = _DumpableModel(
        {
            "screens": [],
            "api_spec": [],
            "data_models": [],
        }
    )
    return SimpleNamespace(run_id=actual_run_id, prd=prd, design_spec=design_spec, qa_feedback=None)


@pytest.mark.asyncio
async def test_execute_retries_with_gemini_after_groq_fallback(monkeypatch):
    monkeypatch.setattr("app.agents.developer.settings.GEMINI_API_KEY", "test-gemini-key")

    providers_seen: list[str] = []

    def fake_init(self, provider: str = "groq"):
        self.name = "Developer Agent"
        self.provider = provider
        self._used_deterministic_fallback = False
        self.max_retries = 3

    async def fake_generate_plan(self, prd, design_spec, qa_feedback):
        providers_seen.append(self.provider)
        if self.provider == "groq":
            self._mark_deterministic_fallback()
        return _fallback_plan(prd=prd, design_spec=design_spec)

    async def fake_generate_file_manifest(self, prd, design_spec, plan, qa_feedback):
        return [
            {
                "path": "frontend/src/app/page.tsx",
                "language": "typescript",
                "description": "Landing page",
            }
        ]

    async def fake_generate_file_contents(self, prd, design_spec, plan, file_manifest, qa_feedback):
        return ({"frontend/src/app/page.tsx": "export default function Page() { return null; }"}, 1)

    monkeypatch.setattr(DeveloperAgent, "__init__", fake_init)
    monkeypatch.setattr(DeveloperAgent, "_generate_plan", fake_generate_plan)
    monkeypatch.setattr(DeveloperAgent, "_generate_file_manifest", fake_generate_file_manifest)
    monkeypatch.setattr(DeveloperAgent, "_generate_file_contents", fake_generate_file_contents)

    agent = DeveloperAgent(provider="groq")
    output = await DeveloperAgent.execute(agent, _build_input())

    assert providers_seen == ["groq", "gemini"]
    assert output["status"] == "completed"
    assert output["files_created"]
    assert output["files_created"][0]["content"]


@pytest.mark.asyncio
async def test_run_developer_agent_returns_final_fallback_when_both_providers_fail(monkeypatch):
    monkeypatch.setattr("app.agents.developer.settings.GEMINI_API_KEY", "test-gemini-key")

    def fake_init(self, provider: str = "groq"):
        self.name = "Developer Agent"
        self.provider = provider
        self._used_deterministic_fallback = False
        self.max_retries = 3

    async def failing_execute(self, input_data):
        raise RuntimeError(f"{self.provider} unavailable")

    monkeypatch.setattr(DeveloperAgent, "__init__", fake_init)
    monkeypatch.setattr(DeveloperAgent, "execute", failing_execute)

    output = await run_developer_agent(_build_input())

    assert output["status"] == "completed"
    assert output["files_created"]
    assert output["implementation_plan"]["required_files"]
