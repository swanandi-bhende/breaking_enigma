"""
Product Manager Agent - Product decision engine.
Produces complete PRD with user stories in Given/When/Then format.
"""

from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ...core.config import settings
from ...core.qdrant import qdrant_manager
from ...schemas.research_pm import (
    PMAgentInput,
    PMAgentOutput,
    PRD,
    ProductVision,
    UserStory,
    AcceptanceCriterion,
    Features,
    Feature,
    BudgetEstimate,
    UserFlowStep,
    ResearchReport,
)
from ...utils.chunking import format_prd_for_embedding


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
8. **Value Projection** - Estimated user value and business value
9. **Basic User Flow** - High-level step-by-step user journey

## Output Requirements:
- You MUST respond with ONLY a valid JSON object matching the schema below
- Do NOT include any explanatory text, markdown code fences, or preamble
- User stories MUST be in Given/When/Then format for acceptance criteria
- Features MUST map to specific user stories

## PRD Schema:
```json
{
  "product_vision": {
    "elevator_pitch": "string",
    "target_user": "string",
    "core_value_proposition": "string",
    "success_definition": "string"
  },
  "user_stories": [
    {
      "id": "US-001",
      "persona": "string",
      "action": "string",
      "outcome": "string",
      "priority": "must-have|should-have|could-have|wont-have",
      "acceptance_criteria": [
        {"given": "string", "when": "string", "then": "string"}
      ],
      "estimated_effort": "XS|S|M|L|XL"
    }
  ],
  "features": {
    "mvp": [
      {
        "id": "F-001",
        "name": "string",
        "description": "string",
        "maps_to_user_stories": ["US-001"],
        "technical_notes": "string"
      }
    ],
    "v1_1": [],
    "v2_0": []
  },
  "budget_estimate": {
    "mvp_engineer_weeks": 0,
    "mvp_cost_usd_range": "string",
    "assumptions": ["string"]
  },
  "user_flow": [
    {
      "step": 1,
      "screen_name": "string",
      "user_action": "string",
      "system_response": "string",
      "next_step": 2
    }
  ]
}
```

## Pain Point Scoring:
Use this formula: score = severity_weight × frequency_weight × market_size
- severity_weights: critical=4, high=3, medium=2, low=1
- frequency_weights: constant=4, frequent=3, occasional=2, rare=1
- market_size: estimated from TAM

Prioritize high-scoring pain points in MVP features.

Return your complete PRD as a JSON object."""


class ProductManagerAgent:
    """PM Agent for PRD generation from research report."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
        )
        self.parser = PydanticOutputParser(pydantic_object=PRD)
        self.max_retries = 3

    def _build_prd_prompt(self, research_report: ResearchReport) -> str:
        """Build the PRD prompt from research report."""
        report_dict = research_report.dict()

        problem = report_dict.get("problem_statement", {})
        market = report_dict.get("market", {})
        personas = report_dict.get("personas", [])
        pain_points = report_dict.get("pain_points", [])
        competitors = report_dict.get("competitors", [])
        viability = report_dict.get("viability", {})
        feasibility = report_dict.get("feasibility", {})

        prompt = f"""## Research Report Summary

### Problem Statement:
{problem.get("core_problem", "")}
Affected Users: {problem.get("affected_users", "")}

### Market:
Industry: {market.get("industry", "")}
TAM: ${market.get("tam_usd", 0):,.0f}
SAM: ${market.get("sam_usd", 0):,.0f}
SOM: ${market.get("som_usd", 0):,.0f}
Growth Rate: {market.get("growth_rate_yoy_percent", 0)}% YoY

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
        """
        Execute the PM Agent.

        Args:
            input_data: PMAgentInput with run_id and research_report

        Returns:
            PMAgentOutput with complete PRD
        """
        run_id = input_data.run_id
        research_report = input_data.research_report

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

                result = await chain.ainvoke({"input": prompt})

                await self._store_embeddings(run_id, result.dict())

                return PMAgentOutput(run_id=run_id, prd=result)

            except Exception as e:
                last_error = e
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

            vectors = await qdrant_manager.embed_texts(story_content)

            await qdrant_manager.store_prd_embeddings(
                run_id=run_id, user_stories=story_texts, vectors=vectors
            )

        except Exception as e:
            print(f"Warning: Failed to store PRD embeddings: {e}")


async def run_pm_agent(input_data: PMAgentInput) -> PMAgentOutput:
    """Main entry point for PM Agent."""
    agent = ProductManagerAgent()
    return await agent.run(input_data)
