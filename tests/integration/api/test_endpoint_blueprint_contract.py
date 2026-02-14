from __future__ import annotations

from pathlib import Path


def test_required_endpoint_paths_exist_in_route_modules():
    base = Path("app/api/v1")
    required_fragments = [
        "/agents/{agent_name}/run",
        "/pipeline/run",
        "/runs",
        "/runs/{run_id}",
        "/runs/{run_id}/retry",
        "/logs/agents",
        "/metrics/agents",
        "/reviews/{entity_type}/{entity_id}/decision",
        "/prompts/{prompt_key}",
        "/runs/{run_id}/manual-override",
    ]
    content = ""
    for file in [base / "agents.py", base / "runs.py", base / "reviews.py", base / "prompts.py"]:
        content += file.read_text(encoding="utf-8")
    for fragment in required_fragments:
        assert fragment in content
