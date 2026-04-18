"""
Documentation Agent — stub for interface compatibility.

Full implementation is Anshul's domain.

Contract: must accept a dict matching DocumentationAgentInput and
return a dict matching DocumentationAgentOutput.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_documentation_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    [STUB] Full implementation owned by Anshul.

    Input shape: DocumentationAgentInput
    Output shape: DocumentationAgentOutput
    """
    raise NotImplementedError(
        "Documentation Agent is not yet implemented. "
        "See backend/app/agents/documentation.py — owned by Anshul."
    )
