from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class ProblemStatement(BaseModel):
    core_problem: str
    affected_users: str
    current_solutions_fail_because: str
    opportunity_window: str


class MarketData(BaseModel):
    tam_usd: float
    sam_usd: float
    som_usd: float
    industry: str
    growth_rate_yoy_percent: float
    key_trends: List[str]


class Persona(BaseModel):
    name: str
    age_range: str
    occupation: str
    goals: List[str]
    frustrations: List[str]
    tech_savviness: Literal["low", "medium", "high"]
    primary_device: str


class PainPoint(BaseModel):
    pain: str
    severity: Literal["low", "medium", "high", "critical"]
    frequency: Literal["rare", "occasional", "frequent", "constant"]
    existing_workaround: Optional[str] = None


class Competitor(BaseModel):
    name: str
    url: str
    positioning: str
    pricing_model: str
    key_features: List[str]
    weaknesses: List[str]
    user_sentiment: Optional[str] = None


class ViabilityData(BaseModel):
    revenue_models: List[str]
    recommended_model: str
    estimated_arpu: str
    go_to_market_strategy: str
    viability_score: int = Field(ge=1, le=10)


class FeasibilityData(BaseModel):
    technical_risks: List[str]
    complexity: Literal["low", "medium", "high"]
    estimated_mvp_weeks: int
    key_dependencies: List[str]
    feasibility_score: int = Field(ge=1, le=10)


class ResearchReport(BaseModel):
    problem_statement: ProblemStatement
    market: MarketData
    personas: List[Persona]
    pain_points: List[PainPoint]
    competitors: List[Competitor]
    viability: ViabilityData
    feasibility: FeasibilityData


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
    acceptance_criteria: List[AcceptanceCriterion]
    estimated_effort: Literal["XS", "S", "M", "L", "XL"]


class Feature(BaseModel):
    id: str
    name: str
    description: str
    maps_to_user_stories: List[str]
    technical_notes: Optional[str] = None


class Features(BaseModel):
    mvp: List[Feature]
    v1_1: List[Feature] = Field(default_factory=list)
    v2_0: List[Feature] = Field(default_factory=list)


class BudgetEstimate(BaseModel):
    mvp_engineer_weeks: float
    mvp_cost_usd_range: str
    assumptions: List[str]


class UserFlowStep(BaseModel):
    step: int
    screen_name: str
    user_action: str
    system_response: str
    next_step: Optional[int] = None


class PRD(BaseModel):
    product_vision: ProductVision
    user_stories: List[UserStory]
    features: Features
    budget_estimate: BudgetEstimate
    user_flow: List[UserFlowStep]


class PMAgentInput(BaseModel):
    run_id: str
    research_report: ResearchReport


class PMAgentOutput(BaseModel):
    run_id: str
    prd: PRD
