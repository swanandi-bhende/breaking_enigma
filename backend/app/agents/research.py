"""
Research Agent — stub for interface compatibility.

Full implementation is Aditya's domain.
This stub is here so that:
  - Nisarg's workflow/graph.py can import it without errors
  - The executor's _load_agent() lazy loader works
  - Unit tests can patch it

When Aditya implements this module, he should replace the stub
body of `run_research_agent()` with real LangChain LLM chains.

Contract: must accept a dict matching ResearchAgentInput and
return a dict matching ResearchAgentOutput.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_research_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    [STUB] Full implementation owned by Aditya.

    Input shape: ResearchAgentInput
    Output shape: ResearchAgentOutput
    """
    raise NotImplementedError(
        "Research Agent is not yet implemented. "
        "See backend/app/agents/research.py — owned by Aditya."
    )
