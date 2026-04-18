"""
QA Agent — stub for interface compatibility.

Full implementation is Anshul's domain.

Contract: must accept a dict matching QAAgentInput and
return a dict matching QAAgentOutput.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_qa_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    [STUB] Full implementation owned by Anshul.

    Input shape: QAAgentInput
    Output shape: QAAgentOutput
    """
    raise NotImplementedError(
        "QA Agent is not yet implemented. "
        "See backend/app/agents/qa.py — owned by Anshul."
    )
