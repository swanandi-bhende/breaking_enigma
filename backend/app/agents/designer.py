"""
Designer Agent — stub for interface compatibility.

Full implementation is Aditya's domain.

Contract: must accept a dict matching DesignerAgentInput and
return a dict matching DesignerAgentOutput.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_designer_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    [STUB] Full implementation owned by Aditya.

    Input shape: DesignerAgentInput
    Output shape: DesignerAgentOutput
    """
    raise NotImplementedError(
        "Designer Agent is not yet implemented. "
        "See backend/app/agents/designer.py — owned by Aditya."
    )
