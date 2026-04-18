"""
Product Manager Agent - Transforms research into complete PRD.
"""

from typing import Dict, Any, List
import logging
import asyncio
import json
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.core.qdrant import qdrant_manager
from app.schemas.research_pm import (
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
from app.utils.chunking import format_prd_for_embedding, extract_json_from_response

logger = logging.getLogger(__name__)


PM_SYSTEM_PROMPT = """You are the Product Manager. Your job is to transform research insights into a Product Requirements Document (PRD).

CRITICAL REQUIREMENTS:
- Respond ONLY with a valid JSON object, nothing else
- Do NOT include any markdown, code fences, or explanatory text
- Do NOT include any preamble or closing text
- All fields MUST be present in the JSON
- Ensure ALL strings are properly escaped and quoted
- Ensure ALL arrays and objects are properly closed with correct commas

Output ONLY the JSON object, starting with { and ending with }."""


def _fallback_prd(research_report: ResearchReport) -> PRD:
    """Build a valid deterministic PRD when LLM calls are unavailable."""
    problem = research_report.problem_statement
    personas = research_report.personas or []
    primary_persona = personas[0].name if personas else "Target User"
    secondary_persona = personas[1].name if len(personas) > 1 else primary_persona

    product_vision = ProductVision(
        elevator_pitch=problem.core_problem,
        target_user=primary_persona,
        core_value_proposition="Deliver clear daily workflows, progress visibility, and actionable recommendations.",
        success_definition="Users complete core tasks consistently and report measurable outcome improvements within 30 days.",
    )

    user_stories = [
        UserStory(
            id="US-001",
            persona=primary_persona,
            action="create an account and onboarding profile",
            outcome="receive a personalized starting plan",
            priority="must-have",
            acceptance_criteria=[
                AcceptanceCriterion(
                    given="a new visitor opens the app",
                    when="they submit onboarding details",
                    then="the system creates a profile and displays a personalized plan",
                )
            ],
            estimated_effort="M",
        ),
        UserStory(
            id="US-002",
            persona=primary_persona,
            action="log daily activity and progress",
            outcome="track consistency and trend improvements",
            priority="must-have",
            acceptance_criteria=[
                AcceptanceCriterion(
                    given="an authenticated user is on dashboard",
                    when="they submit a daily log",
                    then="the entry is saved and reflected in progress charts",
                )
            ],
            estimated_effort="M",
        ),
        UserStory(
            id="US-003",
            persona=secondary_persona,
            action="view weekly summary insights",
            outcome="understand what is working and what needs adjustment",
            priority="should-have",
            acceptance_criteria=[
                AcceptanceCriterion(
                    given="at least 7 days of activity data",
                    when="the user opens weekly insights",
                    then="the system shows trends, highlights, and recommendations",
                )
            ],
            estimated_effort="S",
        ),
        UserStory(
            id="US-004",
            persona=primary_persona,
            action="set reminders and goals",
            outcome="stay accountable and improve adherence",
            priority="should-have",
            acceptance_criteria=[
                AcceptanceCriterion(
                    given="a user configures goal preferences",
                    when="a reminder schedule is saved",
                    then="the user receives reminders at configured intervals",
                )
            ],
            estimated_effort="S",
        ),
        UserStory(
            id="US-005",
            persona=secondary_persona,
            action="share progress with peers",
            outcome="increase motivation through social accountability",
            priority="could-have",
            acceptance_criteria=[
                AcceptanceCriterion(
                    given="a user has progress data",
                    when="they choose a sharing option",
                    then="a summary card is generated and shared safely",
                )
            ],
            estimated_effort="M",
        ),
    ]

    features = Features(
        mvp=[
            Feature(
                id="F-001",
                name="Onboarding and Profile",
                description="Capture preferences and generate personalized plan baseline.",
                maps_to_user_stories=["US-001"],
                technical_notes="Store profile preferences and defaults in typed schema.",
            ),
            Feature(
                id="F-002",
                name="Daily Tracking",
                description="Allow users to log activity and monitor daily consistency.",
                maps_to_user_stories=["US-002"],
                technical_notes="Implement idempotent create/update operations for logs.",
            ),
            Feature(
                id="F-003",
                name="Weekly Insights",
                description="Summarize trends and recommendation highlights.",
                maps_to_user_stories=["US-003"],
                technical_notes="Precompute aggregates for dashboard responsiveness.",
            ),
        ],
        v1_1=[
            Feature(
                id="F-004",
                name="Goals and Reminders",
                description="Enable configurable goals, reminders, and streak support.",
                maps_to_user_stories=["US-004"],
                technical_notes="Notification delivery with retry and timezone support.",
            )
        ],
        v2_0=[
            Feature(
                id="F-005",
                name="Social Sharing",
                description="Share progress summaries with peers and accountability groups.",
                maps_to_user_stories=["US-005"],
                technical_notes="Apply privacy controls and scoped sharing tokens.",
            )
        ],
    )

    budget = BudgetEstimate(
        mvp_engineer_weeks=6.0,
        mvp_cost_usd_range="$45k-$80k",
        assumptions=[
            "Small full-stack team with shared infrastructure",
            "Reusing existing auth and deployment foundation",
            "One target platform for MVP with progressive enhancement",
        ],
    )

    user_flow = [
        UserFlowStep(step=1, screen_name="Landing", user_action="Open app", system_response="Display value proposition and CTA", next_step=2),
        UserFlowStep(step=2, screen_name="Signup", user_action="Create account", system_response="Provision user profile", next_step=3),
        UserFlowStep(step=3, screen_name="Onboarding", user_action="Submit goals/preferences", system_response="Generate initial plan", next_step=4),
        UserFlowStep(step=4, screen_name="Dashboard", user_action="Log daily activity", system_response="Persist logs and refresh insights", next_step=5),
        UserFlowStep(step=5, screen_name="Insights", user_action="Review weekly progress", system_response="Render trends and recommendations", next_step=None),
    ]

    return PRD(
        product_vision=product_vision,
        user_stories=user_stories,
        features=features,
        budget_estimate=budget,
        user_flow=user_flow,
    )


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
        """Build concise PRD prompt from research."""
        r = research_report.dict()
        problem = r.get("problem_statement", {})
        market = r.get("market", {})
        personas = r.get("personas", [])
        pain_points = r.get("pain_points", [])
        viability = r.get("viability", {})
        feasibility = r.get("feasibility", {})

        persona_names = ", ".join([p.get('name', '') for p in personas[:3]])
        top_pains = "\n".join([f"- {pp.get('pain', '')}" for pp in pain_points[:5]])

        schema_example = """{
  "product_vision": {
    "elevator_pitch": "One sentence overview",
    "target_user": "Primary user persona",
    "core_value_proposition": "Key benefit",
    "success_definition": "How success is measured"
  },
    "user_stories": [
        {
            "id": "US-001",
            "persona": "Persona name",
            "action": "user action",
            "outcome": "desired result",
            "priority": "must-have",
            "acceptance_criteria": [
                {"given": "precondition", "when": "action", "then": "result"}
            ],
            "estimated_effort": "M"
        },
        {
            "id": "US-002",
            "persona": "Persona name",
            "action": "user action",
            "outcome": "desired result",
            "priority": "should-have",
            "acceptance_criteria": [
                {"given": "precondition", "when": "action", "then": "result"}
            ],
            "estimated_effort": "S"
        },
        {
            "id": "US-003",
            "persona": "Persona name",
            "action": "user action",
            "outcome": "desired result",
            "priority": "could-have",
            "acceptance_criteria": [
                {"given": "precondition", "when": "action", "then": "result"}
            ],
            "estimated_effort": "XS"
        }
    ],
  "features": {
    "mvp": [{"id": "F-001", "name": "Feature", "description": "description", "maps_to_user_stories": ["US-001"], "technical_notes": "notes"}],
    "v1_1": [{"id": "F-002", "name": "Feature", "description": "description", "maps_to_user_stories": ["US-002"], "technical_notes": "notes"}],
    "v2_0": [{"id": "F-003", "name": "Feature", "description": "description", "maps_to_user_stories": ["US-003"], "technical_notes": "notes"}]
  },
  "budget_estimate": {
    "mvp_engineer_weeks": 4.0,
    "mvp_cost_usd_range": "$50k-$80k",
    "assumptions": ["team composition", "use of frameworks"]
  },
  "user_flow": [
        {"step": 1, "screen_name": "Landing", "user_action": "User lands on page", "system_response": "Show onboarding", "next_step": 2},
        {"step": 2, "screen_name": "Signup", "user_action": "User signs up", "system_response": "Create account", "next_step": 3},
        {"step": 3, "screen_name": "Dashboard", "user_action": "User views dashboard", "system_response": "Load user data", "next_step": null}
    ]
}"""

        prompt = f"""Product Brief:
Problem: {problem.get('core_problem', '')}
Affected Users: {problem.get('affected_users', '')}
Market TAM: ${market.get('tam_usd', 0):,.0f} with {market.get('growth_rate_yoy_percent', 0)}% YoY growth
Primary Personas: {persona_names}
Recommended Revenue Model: {viability.get('recommended_model', 'subscription')}
Estimated MVP Timeline: {feasibility.get('estimated_mvp_weeks', 0)} weeks

Top Pain Points to Address:
{top_pains}

Create a Product Requirements Document (PRD) in JSON format matching this schema:
{schema_example}

Requirements:
1. Include at least 5 user stories with proper Given/When/Then acceptance criteria
2. Map all features to user stories
3. Provide realistic engineering estimates
4. Group features into MVP, v1.1, and v2.0 phases
5. Create a complete user flow of 5-7 steps

IMPORTANT FORMAT REQUIREMENTS:
- User story IDs must follow the pattern: US-001, US-002, US-003 (US- followed by exactly 3 digits)
- User story priorities MUST be exactly one of: "must-have", "should-have", "could-have", or "wont-have"
- User story effort estimates MUST be exactly one of: "XS", "S", "M", "L", or "XL"
- Feature IDs should follow the pattern: F-001, F-002, F-003
- User flow steps must be sequential from 1, with the final step having next_step: null
- Keep field names snake_case exactly as shown in schema"""

        return prompt

    async def run(self, input_data: PMAgentInput | Dict[str, Any]) -> PMAgentOutput:
        """Execute PM Agent with exponential backoff for rate limits."""
        import asyncio
        import json
        
        if isinstance(input_data, dict):
            input_data = PMAgentInput.model_validate(input_data)

        run_id = input_data.run_id
        research_report = input_data.research_report

        prompt = self._build_prd_prompt(research_report)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.llm.ainvoke(
                    [
                        ("system", PM_SYSTEM_PROMPT),
                        ("human", prompt),
                    ]
                )
                
                # Extract and parse JSON with multiple fallback strategies
                response_content = response.content
                logger.info(f"[product_manager] Raw response length: {len(response_content)} chars")
                
                json_obj = None
                
                # Strategy 1: Try extract_json_from_response
                try:
                    json_obj = extract_json_from_response(response_content)
                    logger.info(f"[product_manager] Successfully parsed JSON using extract_json_from_response")
                except Exception as e1:
                    logger.warning(f"[product_manager] extract_json_from_response failed: {str(e1)[:100]}")
                    
                    # Strategy 2: Try direct JSON parsing
                    try:
                        json_obj = json.loads(response_content.strip())
                        logger.info(f"[product_manager] Successfully parsed JSON using direct parsing")
                    except Exception as e2:
                        logger.warning(f"[product_manager] Direct JSON parsing failed: {str(e2)[:100]}")
                        
                        # Strategy 3: Find and extract JSON object
                        try:
                            import re
                            # Find the first { and last } to extract potential JSON
                            start_idx = response_content.find('{')
                            end_idx = response_content.rfind('}')
                            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                                potential_json = response_content[start_idx:end_idx+1]
                                json_obj = json.loads(potential_json)
                                logger.info(f"[product_manager] Successfully parsed JSON using bracket extraction")
                            else:
                                raise ValueError("Could not find JSON brackets in response")
                        except Exception as e3:
                            logger.error(f"[product_manager] Bracket extraction failed: {str(e3)[:100]}")
                            raise ValueError(f"Could not parse JSON from response after all strategies: {e1}")
                
                if json_obj is None:
                    raise ValueError("JSON parsing returned None")
                
                # Validate required fields
 
                required_fields = ["product_vision", "user_stories", "features", "budget_estimate", "user_flow"]
                missing_fields = [f for f in required_fields if f not in json_obj]
                if missing_fields:
                    raise ValueError(f"Missing fields: {missing_fields}")
                
                # Validate user stories and user flow
                if len(json_obj.get("user_stories", [])) < 3:
                    raise ValueError(f"Need at least 3 user stories, got {len(json_obj.get('user_stories', []))}")
                
                if len(json_obj.get("user_flow", [])) < 3:
                    raise ValueError(f"Need at least 3 user flow steps, got {len(json_obj.get('user_flow', []))}")
                
                logger.info(f"[product_manager] JSON validation passed, creating PRD")
                try:
                    result = PRD(**json_obj)
                except Exception as validation_error:
                    logger.error(f"[product_manager] Pydantic validation error: {str(validation_error)[:500]}")
                    logger.error(f"[product_manager] Full JSON keys: {list(json_obj.keys())}")
                    raise

                await self._store_embeddings(run_id, result.dict())

                logger.info(f"[product_manager] Generated PRD with {len(result.user_stories)} user stories")
                return PMAgentOutput(run_id=run_id, prd=result)

            except Exception as e:
                error_str = str(e)
                last_error = e
                logger.error(f"[product_manager] Attempt {attempt+1}/{self.max_retries} failed: {error_str[:200]}")
                
                # Handle rate limit with exponential backoff
                if "rate_limit_exceeded" in error_str or "429" in error_str:
                    wait_time = min(2 ** attempt * 10, 120)
                    logger.warning(f"[product_manager] Rate limit, waiting {wait_time}s before retry {attempt+1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                
                # Retry on other errors
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
                    continue

        logger.error(
            "[product_manager] Exhausted retries, returning deterministic fallback PRD: %s",
            str(last_error)[:300],
        )
        fallback_prd = _fallback_prd(research_report)
        await self._store_embeddings(run_id, fallback_prd.dict())
        return PMAgentOutput(run_id=run_id, prd=fallback_prd)

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


async def run_pm_agent(input_data: PMAgentInput | Dict[str, Any]) -> Dict[str, Any]:
  """Main entry point for PM Agent.

  The workflow executor validates raw dictionaries, so return serialized
  output rather than a pydantic model instance.
  """
  agent = ProductManagerAgent()
  result = await agent.run(input_data)
  return result.model_dump(mode="json")
