"""Bridge between the Textual UI and the existing runtime workflow."""

from __future__ import annotations

from typing import Any, Callable

from src import runtime

TuiEventCallback = Callable[[dict[str, Any]], None]


def run_tui_task(
    config_path: str,
    input_type: str,
    items: list[str],
    overrides: dict[str, Any],
    event_callback: TuiEventCallback,
) -> dict[str, Any]:
    """Run a UI-submitted translation task through the existing runtime."""
    runtime_overrides = dict(overrides)
    project_items: list[str] = []
    project_url_items: list[str] = []

    if input_type == "arxiv":
        runtime_overrides["paper_list"] = list(items)
    elif input_type == "local":
        runtime_overrides["paper_list"] = []
        project_items = list(items)
    elif input_type == "remote":
        runtime_overrides["paper_list"] = []
        project_url_items = list(items)
    else:
        raise ValueError(f"Unsupported input type: {input_type}")

    config = runtime.load_runtime_config(config_path=config_path, overrides=runtime_overrides)
    projects, config, projects_dir, output_dir = runtime.prepare_projects(
        config=config,
        project_items=project_items,
        project_url_items=project_url_items,
        all_existing=False,
    )
    project_status = runtime.run_projects(
        config=config,
        projects=projects,
        output_dir=output_dir,
        event_callback=event_callback,
    )

    return {
        "config": config,
        "projects": projects,
        "projects_dir": projects_dir,
        "output_dir": output_dir,
        "completed_projects": project_status["completed_projects"],
        "failed_projects": project_status["failed_projects"],
    }
