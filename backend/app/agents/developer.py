"""
Developer Agent — stub for interface compatibility.

Full implementation is Anshul's domain.

Contract: must accept a dict matching DeveloperAgentInput and
return a dict matching DeveloperAgentOutput.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_developer_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    [STUB] Full implementation owned by Anshul.

    Input shape: DeveloperAgentInput
    Output shape: DeveloperAgentOutput
    """
    raise NotImplementedError(
        "Developer Agent is not yet implemented. "
        "See backend/app/agents/developer.py — owned by Anshul."
    )
