"""
Local schema aliases kept for backward-compatibility with research.py,
product_manager.py, and designer.py.

The authoritative schemas are in app/schemas/agents.py (Nisarg's).
These match exactly — same field names, same types, same constraints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class ProblemStatement(BaseModel):
    core_problem: str
    affected_users: str
    current_solutions_fail_because: str
    opportunity_window: str


class MarketData(BaseModel):
    tam_usd: Optional[float] = None
    sam_usd: Optional[float] = None
    som_usd: Optional[float] = None
    industry: str
    growth_rate_yoy_percent: Optional[float] = None
    key_trends: List[str] = Field(default_factory=list)


class Persona(BaseModel):
    name: str
    age_range: str
    occupation: str
    goals: List[str] = Field(default_factory=list)
    frustrations: List[str] = Field(default_factory=list)
    tech_savviness: Literal["low", "medium", "high"]
    primary_device: str


class PainPoint(BaseModel):
    pain: str
    severity: Literal["low", "medium", "high", "critical"]
    frequency: Literal["rare", "occasional", "frequent", "constant"]
    existing_workaround: Optional[str] = None


class Competitor(BaseModel):
    name: str
    url: Optional[str] = None  # Optional — some competitors have no public URL
    positioning: str
    pricing_model: str
    key_features: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    user_sentiment: Optional[str] = None


class Viability(BaseModel):
    revenue_models: List[str] = Field(default_factory=list)
    recommended_model: str
    estimated_arpu: Optional[str] = None
    go_to_market_strategy: str
    viability_score: int = Field(ge=1, le=10)


# Alias for backward-compat
ViabilityData = Viability


class Feasibility(BaseModel):
    technical_risks: List[str] = Field(default_factory=list)
    complexity: Literal["low", "medium", "high"]
    estimated_mvp_weeks: int
    key_dependencies: List[str] = Field(default_factory=list)
    feasibility_score: int = Field(ge=1, le=10)


# Alias for backward-compat
FeasibilityData = Feasibility


class ResearchReport(BaseModel):
    problem_statement: ProblemStatement
    market: MarketData
    personas: List[Persona] = Field(..., min_length=1)
    pain_points: List[PainPoint] = Field(..., min_length=1)
    competitors: List[Competitor] = Field(default_factory=list)
    viability: Viability
    feasibility: Feasibility


class ResearchAgentInput(BaseModel):
    run_id: str
    project_brief: dict
    tools_available: List[str] = Field(
        default_factory=lambda: ["web_search", "serp_api"]
    )


class ResearchAgentOutput(BaseModel):
    run_id: str
    research_report: ResearchReport
    embedding_ids: List[str] = Field(default_factory=list)


class ProductVision(BaseModel):
    elevator_pitch: str
    target_user: str
    core_value_proposition: str
    success_definition: str


class AcceptanceCriterion(BaseModel):
    given: str
    when: str
    then: str


class UserStory(BaseModel):
    id: str = Field(pattern=r"^US-[0-9]{3}$")
    persona: str
    action: str
    outcome: str
    priority: Literal["must-have", "should-have", "could-have", "wont-have"]
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list)
    estimated_effort: Optional[Literal["XS", "S", "M", "L", "XL"]] = None


class Feature(BaseModel):
    id: str
    name: str
    description: str
    maps_to_user_stories: List[str] = Field(default_factory=list)
    technical_notes: Optional[str] = None


class Features(BaseModel):
    mvp: List[Feature] = Field(default_factory=list)
    v1_1: List[Feature] = Field(default_factory=list)
    v2_0: List[Feature] = Field(default_factory=list)


# Alias to match agents.py FeatureSet
FeatureSet = Features


class BudgetEstimate(BaseModel):
    mvp_engineer_weeks: float
    mvp_cost_usd_range: str
    assumptions: List[str] = Field(default_factory=list)


class UserFlowStep(BaseModel):
    step: int
    screen_name: str
    user_action: str
    system_response: str
    next_step: Optional[int] = None


class PRD(BaseModel):
    product_vision: ProductVision
    user_stories: List[UserStory] = Field(default_factory=list)
    features: Features = Field(default_factory=Features)
    budget_estimate: Optional[BudgetEstimate] = None
    user_flow: List[UserFlowStep] = Field(default_factory=list)


class PMAgentInput(BaseModel):
    run_id: str
    research_report: ResearchReport


class PMAgentOutput(BaseModel):
    run_id: str
    prd: PRD
