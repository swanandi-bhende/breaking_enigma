"""Agent package exports with lazy imports to avoid eager dependency loading."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "run_research_agent",
    "ResearchAgent",
    "run_pm_agent",
    "ProductManagerAgent",
    "run_designer_agent",
    "DesignerAgent",
]


def __getattr__(name: str) -> Any:
    mapping = {
        "run_research_agent": ("app.agents.research", "run_research_agent"),
        "ResearchAgent": ("app.agents.research", "ResearchAgent"),
        "run_pm_agent": ("app.agents.product_manager", "run_pm_agent"),
        "ProductManagerAgent": ("app.agents.product_manager", "ProductManagerAgent"),
        "run_designer_agent": ("app.agents.designer", "run_designer_agent"),
        "DesignerAgent": ("app.agents.designer", "DesignerAgent"),
    }
    if name not in mapping:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = mapping[name]
    module = import_module(module_name)
    return getattr(module, attr_name)
