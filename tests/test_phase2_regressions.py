from __future__ import annotations

from pathlib import Path


MODULE_PATHS = [
    "app/main.py",
    "app/api/v1/router.py",
    "app/tasks/celery_app.py",
    "app/tasks/agent_tasks.py",
]


def test_future_import_preamble_exists_once() -> None:
    for module_path in MODULE_PATHS:
        source = Path(module_path).read_text(encoding="utf-8")
        assert source.startswith("from __future__ import annotations\n")
        assert source.count("from __future__ import annotations") == 1


def test_phase2_modules_are_importable() -> None:
    import app.main as main_module
    import app.api.v1.router as router_module
    import app.tasks.celery_app as celery_module
    import app.tasks.agent_tasks as tasks_module

    assert main_module.app is not None
    assert router_module.api_router is not None
    assert celery_module.celery_app is not None
    assert tasks_module.execute_agent_task is not None
