"""
Product Manager Agent — Product decision engine.
Produces complete PRD with user stories in Given/When/Then format.

Entry-point: run_pm_agent(input_dict: dict) -> dict
"""

import logging
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.core.llm import llm_client
from app.core.qdrant import qdrant_manager
from app.schemas.research_pm import (
    PMAgentInput,
    PMAgentOutput,
    PRD,
    ResearchReport,
)

logger = logging.getLogger(__name__)


PM_SYSTEM_PROMPT = """You are the Product Manager Agent in an autonomous product development system.
Your role is to transform research findings into a complete, implementation-ready Product Requirements Document (PRD).

## Your Responsibilities:
1. **Define Product Direction** - What are we building, who is it for, why will they use it
2. **Pain Point Prioritization** - Rank pain points by severity × frequency × market size
3. **User Stories Generation** - Full set in "As a [persona], I want to [action] so that [outcome]" format
4. **Acceptance Criteria** - Specific, testable criteria in Given/When/Then format for every user story
5. **Solution Design** - Concrete approach mapped to prioritized pain points
6. **Feature Definition** - Group features as Must-Have (MVP), Should-Have (v1.1), Could-Have (v2.0)
7. **Budget Estimation** - Rough build cost in engineer-weeks
8. **Basic User Flow** - High-level step-by-step user journey

## Output Requirements:
- You MUST respond with ONLY a valid JSON object matching the schema below
- Do NOT include any explanatory text, markdown code fences, or preamble
- User stories MUST be in Given/When/Then format for acceptance criteria
- User story IDs MUST match format "US-001", "US-002", etc.
- Features MUST map to specific user stories

## PRD Schema:
```json
{{
  "product_vision": {{
    "elevator_pitch": "string",
    "target_user": "string",
    "core_value_proposition": "string",
    "success_definition": "string"
  }},
  "user_stories": [
    {{
      "id": "US-001",
      "persona": "string",
      "action": "string",
      "outcome": "string",
      "priority": "must-have|should-have|could-have|wont-have",
      "acceptance_criteria": [
        {{"given": "string", "when": "string", "then": "string"}}
      ],
      "estimated_effort": "XS|S|M|L|XL"
    }}
  ],
  "features": {{
    "mvp": [
      {{
        "id": "F-001",
        "name": "string",
        "description": "string",
        "maps_to_user_stories": ["US-001"],
        "technical_notes": "string"
      }}
    ],
    "v1_1": [],
    "v2_0": []
  }},
  "budget_estimate": {{
    "mvp_engineer_weeks": 12,
    "mvp_cost_usd_range": "$50,000-$80,000",
    "assumptions": ["string"]
  }},
  "user_flow": [
    {{
      "step": 1,
      "screen_name": "string",
      "user_action": "string",
      "system_response": "string",
      "next_step": 2
    }}
  ]
}}
```

Return your complete PRD as a JSON object."""


class ProductManagerAgent:
    """PM Agent for PRD generation from research report."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        self.parser = PydanticOutputParser(pydantic_object=PRD)
        self.max_retries = 3

    def _build_prd_prompt(self, research_report: ResearchReport) -> str:
        """Build the PRD prompt from research report."""
        report_dict = research_report.model_dump()

        problem = report_dict.get("problem_statement", {})
        market = report_dict.get("market", {})
        personas = report_dict.get("personas", [])
        pain_points = report_dict.get("pain_points", [])
        competitors = report_dict.get("competitors", [])
        viability = report_dict.get("viability", {})
        feasibility = report_dict.get("feasibility", {})

        tam = market.get("tam_usd") or 0
        sam = market.get("sam_usd") or 0
        som = market.get("som_usd") or 0
        growth = market.get("growth_rate_yoy_percent") or 0

        prompt = f"""## Research Report Summary

### Problem Statement:
{problem.get("core_problem", "")}
Affected Users: {problem.get("affected_users", "")}

### Market:
Industry: {market.get("industry", "")}
TAM: ${tam:,.0f}
SAM: ${sam:,.0f}
SOM: ${som:,.0f}
Growth Rate: {growth}% YoY

### Target Personas:
{chr(10).join([f"- {p.get('name', '')}: {p.get('occupation', '')}" for p in personas])}

### Pain Points (to address in MVP):
{chr(10).join([f"- {pp.get('pain', '')} (Severity: {pp.get('severity', '')}, Freq: {pp.get('frequency', '')})" for pp in pain_points[:5]])}

### Competitors:
{chr(10).join([f"- {c.get('name', '')}: {c.get('positioning', '')}" for c in competitors[:3]])}

### Viability:
Recommended Revenue Model: {viability.get("recommended_model", "")}
Viability Score: {viability.get("viability_score", 0)}/10

### Feasibility:
Complexity: {feasibility.get("complexity", "")}
Estimated MVP Weeks: {feasibility.get("estimated_mvp_weeks", 0)}

---

Now create a comprehensive PRD based on this research.
{self.parser.get_format_instructions()}"""

        return prompt

    async def run(self, input_data: PMAgentInput) -> PMAgentOutput:
        run_id = str(input_data.run_id)
        research_report = input_data.research_report

        try:
            from app.core.redis import publish_log_line
            await publish_log_line(run_id, "product_manager", "Analysing research report...")
        except Exception:
            pass

        prompt = self._build_prd_prompt(research_report)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                chain = (
                    ChatPromptTemplate.from_messages(
                        [("system", PM_SYSTEM_PROMPT), ("human", "{input}")]
                    )
                    | self.llm
                    | self.parser
                )

                try:
                    from app.core.redis import publish_log_line
                    await publish_log_line(run_id, "product_manager", f"Generating PRD (attempt {attempt + 1})...")
                except Exception:
                    pass

                result = await chain.ainvoke({"input": prompt})

                # Store PRD embeddings for QA traceability
                await self._store_embeddings(run_id, result.model_dump())

                try:
                    from app.core.redis import publish_log_line
                    stories_count = len(result.user_stories)
                    await publish_log_line(run_id, "product_manager", f"PRD generated with {stories_count} user stories ✓")
                except Exception:
                    pass

                return PMAgentOutput(run_id=run_id, prd=result)

            except Exception as e:
                last_error = e
                logger.warning(f"PM attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    continue

        raise Exception(
            f"PM Agent failed after {self.max_retries} attempts: {last_error}"
        )

    async def _store_embeddings(self, run_id: str, prd: Dict[str, Any]) -> None:
        """Store PRD user stories in Qdrant for QA traceability."""
        try:
            user_stories = prd.get("user_stories", [])
            if not user_stories:
                return

            story_texts = [
                {
                    "id": us.get("id", f"US-{i:03d}"),
                    "persona": us.get("persona", ""),
                    "action": us.get("action", ""),
                    "outcome": us.get("outcome", ""),
                }
                for i, us in enumerate(user_stories)
            ]

            story_content = [
                f"{s['persona']} {s['action']} {s['outcome']}" for s in story_texts
            ]

            # Use llm_client for embeddings (not qdrant_manager)
            vectors = await llm_client.embed_texts(story_content)

            await qdrant_manager.store_prd_embeddings(
                run_id=str(run_id), user_stories=story_texts, vectors=vectors
            )

        except Exception as e:
            logger.warning(f"Warning: Failed to store PRD embeddings: {e}")


async def run_pm_agent(input_dict: dict) -> dict:
    """
    Main entry-point for PM Agent.
    Accepts a plain dict (from executor), returns a plain dict.
    """
    input_data = PMAgentInput.model_validate(input_dict)
    agent = ProductManagerAgent()
    result = await agent.run(input_data)
    return result.model_dump(mode="json")
