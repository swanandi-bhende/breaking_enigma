"""
Product Manager Agent — stub for interface compatibility.

Full implementation is Aditya's domain.

Contract: must accept a dict matching PMAgentInput and
return a dict matching PMAgentOutput.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_pm_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    [STUB] Full implementation owned by Aditya.

    Input shape: PMAgentInput
    Output shape: PMAgentOutput
    """
    raise NotImplementedError(
        "PM Agent is not yet implemented. "
        "See backend/app/agents/product_manager.py — owned by Aditya."
    )
