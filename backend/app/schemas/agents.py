"""
Pydantic v2 schemas for all ADWF agent inputs and outputs.

These schemas are the machine-to-machine contracts between agents.
Every agent's input is validated against the previous agent's output schema
BEFORE being passed downstream — enforced by the executor wrapper.

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════════════════════
# Shared / Primitive types
# ════════════════════════════════════════════════════════════════════════════


class TargetPlatform(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    API_ONLY = "api-only"


class RunState(str, Enum):
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"


class PhaseStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PhaseInfo(BaseModel):
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    iteration: int = 0
    error: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ════════════════════════════════════════════════════════════════════════════


class OrchestratorConfig(BaseModel):
    max_qa_iterations: int = Field(default=3, ge=1, le=10)
    skip_agents: List[str] = Field(default_factory=list)
    human_checkpoints: List[str] = Field(default_factory=list)
    llm_model: str = "gpt-4o"
    target_platform: TargetPlatform = TargetPlatform.WEB


class OrchestratorInput(BaseModel):
    run_id: UUID
    idea: str = Field(..., min_length=10, max_length=1000)
    config: OrchestratorConfig = Field(default_factory=OrchestratorConfig)


class ProjectBrief(BaseModel):
    title: str
    normalized_idea: str
    domain: str
    target_platform: str


class OrchestratorOutput(BaseModel):
    run_id: UUID
    run_state: RunState
    project_brief: ProjectBrief
    phases: Dict[str, PhaseInfo] = Field(default_factory=dict)
    artifact_urls: Dict[str, str] = Field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════════════
# Research Agent
# ════════════════════════════════════════════════════════════════════════════


class ResearchAgentInput(BaseModel):
    run_id: UUID
    project_brief: ProjectBrief
    tools_available: List[str] = Field(
        default_factory=lambda: ["web_search", "serp_api", "crunchbase_lookup"]
    )


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


class SavvinessLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Persona(BaseModel):
    name: str
    age_range: str
    occupation: str
    goals: List[str] = Field(default_factory=list)
    frustrations: List[str] = Field(default_factory=list)
    tech_savviness: SavvinessLevel
    primary_device: str


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PainFrequency(str, Enum):
    RARE = "rare"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"
    CONSTANT = "constant"


class PainPoint(BaseModel):
    pain: str
    severity: Severity
    frequency: PainFrequency
    existing_workaround: Optional[str] = None


class Competitor(BaseModel):
    name: str
    url: Optional[str] = None
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
    viability_score: int = Field(..., ge=1, le=10)


class Feasibility(BaseModel):
    technical_risks: List[str] = Field(default_factory=list)
    complexity: SavvinessLevel  # reuses low/medium/high
    estimated_mvp_weeks: int
    key_dependencies: List[str] = Field(default_factory=list)
    feasibility_score: int = Field(..., ge=1, le=10)


class ResearchReport(BaseModel):
    problem_statement: ProblemStatement
    market: MarketData
    personas: List[Persona] = Field(..., min_length=1)
    pain_points: List[PainPoint] = Field(..., min_length=1)
    competitors: List[Competitor] = Field(default_factory=list)
    viability: Viability
    feasibility: Feasibility


class ResearchAgentOutput(BaseModel):
    run_id: UUID
    research_report: ResearchReport
    embedding_ids: List[str] = Field(default_factory=list)


# ════════════════════════════════════════════════════════════════════════════
# PM Agent
# ════════════════════════════════════════════════════════════════════════════


class PMAgentInput(BaseModel):
    run_id: UUID
    research_report: ResearchReport


class Priority(str, Enum):
    MUST_HAVE = "must-have"
    SHOULD_HAVE = "should-have"
    COULD_HAVE = "could-have"
    WONT_HAVE = "wont-have"


class Effort(str, Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class AcceptanceCriterion(BaseModel):
    given: str
    when: str
    then: str


class UserStory(BaseModel):
    id: str = Field(..., pattern=r"^US-\d{3}$")
    persona: str
    action: str
    outcome: str
    priority: Priority
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list)
    estimated_effort: Optional[Effort] = None


class Feature(BaseModel):
    id: str
    name: str
    description: str
    maps_to_user_stories: List[str] = Field(default_factory=list)
    technical_notes: Optional[str] = None


class FeatureSet(BaseModel):
    mvp: List[Feature] = Field(default_factory=list)
    v1_1: List[Feature] = Field(default_factory=list)
    v2_0: List[Feature] = Field(default_factory=list)


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


class ProductVision(BaseModel):
    elevator_pitch: str
    target_user: str
    core_value_proposition: str
    success_definition: str


class PRD(BaseModel):
    product_vision: ProductVision
    user_stories: List[UserStory] = Field(default_factory=list)
    features: FeatureSet = Field(default_factory=FeatureSet)
    budget_estimate: Optional[BudgetEstimate] = None
    user_flow: List[UserFlowStep] = Field(default_factory=list)


class PMAgentOutput(BaseModel):
    run_id: UUID
    prd: PRD


# ════════════════════════════════════════════════════════════════════════════
# Designer Agent
# ════════════════════════════════════════════════════════════════════════════


class DesignerAgentInput(BaseModel):
    run_id: UUID
    prd: PRD
    research_context_embedding_ids: List[str] = Field(default_factory=list)


class ComponentType(str, Enum):
    LAYOUT = "layout"
    FORM = "form"
    DISPLAY = "display"
    NAVIGATION = "navigation"
    FEEDBACK = "feedback"


class UIComponent(BaseModel):
    component_name: str
    type: ComponentType
    props: Dict[str, Any] = Field(default_factory=dict)
    state_dependencies: List[str] = Field(default_factory=list)


class Screen(BaseModel):
    screen_id: str
    screen_name: str
    route: str
    purpose: Optional[str] = None
    components: List[UIComponent] = Field(default_factory=list)
    ux_decisions: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)
    wireframe_description: Optional[str] = None


class InteractionFlow(BaseModel):
    flow_id: str
    flow_name: str
    trigger: str
    steps: List[str] = Field(default_factory=list)
    happy_path_end: str
    failure_paths: List[str] = Field(default_factory=list)


class SystemArchitecture(BaseModel):
    frontend: str
    backend: str
    database: str
    cache: str
    external_services: List[str] = Field(default_factory=list)
    communication_patterns: Dict[str, str] = Field(default_factory=dict)


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class RequestBodySpec(BaseModel):
    content_type: str = "application/json"
    schema_def: Dict[str, Any] = Field(default_factory=dict, alias="schema")
    validation_rules: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ResponseSpec(BaseModel):
    description: str
    schema_def: Dict[str, Any] = Field(default_factory=dict, alias="schema")
    example: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class APIEndpoint(BaseModel):
    endpoint_id: str
    method: HttpMethod
    path: str
    auth_required: bool = True
    description: Optional[str] = None
    request_body: Optional[RequestBodySpec] = None
    responses: Dict[str, ResponseSpec] = Field(default_factory=dict)
    rate_limit: Optional[str] = None
    maps_to_user_stories: List[str] = Field(default_factory=list)


class DBField(BaseModel):
    name: str
    type: str
    nullable: bool = True
    unique: bool = False
    indexed: bool = False
    foreign_key: Optional[str] = None
    default: Optional[str] = None


class RelationType(str, Enum):
    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_MANY = "many-to-many"


class Relationship(BaseModel):
    type: RelationType
    with_entity: str
    foreign_key: str


class DataModel(BaseModel):
    entity_name: str
    table_name: str
    fields: List[DBField] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)


class DesignSpec(BaseModel):
    screens: List[Screen] = Field(default_factory=list)
    interaction_flows: List[InteractionFlow] = Field(default_factory=list)
    system_architecture: SystemArchitecture
    api_spec: List[APIEndpoint] = Field(default_factory=list)
    data_models: List[DataModel] = Field(default_factory=list)


class DesignerAgentOutput(BaseModel):
    run_id: UUID
    design_spec: DesignSpec


# ════════════════════════════════════════════════════════════════════════════
# Developer Agent
# ════════════════════════════════════════════════════════════════════════════


class QAFeedback(BaseModel):
    iteration: int
    failed_tests: List[Dict[str, Any]] = Field(default_factory=list)
    bugs: List[Dict[str, Any]] = Field(default_factory=list)
    fix_instructions: List[Dict[str, Any]] = Field(default_factory=list)


class DeveloperAgentInput(BaseModel):
    run_id: UUID
    design_spec: DesignSpec
    prd: PRD
    qa_feedback: Optional[QAFeedback] = None


class GeneratedFile(BaseModel):
    path: str
    purpose: str
    content: str
    language: Optional[str] = None
    maps_to_endpoint_ids: List[str] = Field(default_factory=list)
    maps_to_screen_ids: List[str] = Field(default_factory=list)


class SkippedFeature(BaseModel):
    feature: str
    reason: str


class DeveloperSelfCheck(BaseModel):
    schema_consistent: bool = False
    all_routes_implemented: bool = False
    feature_coverage_percent: float = 0.0
    test_coverage_percent: float = 0.0
    issues_found: List[str] = Field(default_factory=list)


class DeveloperStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class DeveloperAgentOutput(BaseModel):
    run_id: UUID
    task_id: str
    status: DeveloperStatus
    summary: str
    files_created: List[GeneratedFile] = Field(default_factory=list)
    features_implemented: List[str] = Field(default_factory=list)
    features_skipped: List[SkippedFeature] = Field(default_factory=list)
    tests_written: List[str] = Field(default_factory=list)
    tech_debt_logged: List[str] = Field(default_factory=list)
    self_check_results: Optional[DeveloperSelfCheck] = None


# ════════════════════════════════════════════════════════════════════════════
# QA Agent
# ════════════════════════════════════════════════════════════════════════════


class QAAgentInput(BaseModel):
    run_id: UUID
    developer_output: DeveloperAgentOutput
    design_spec: DesignSpec
    prd: PRD
    iteration: int = 1


class CoverageStatus(str, Enum):
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class CriterionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNTESTABLE = "UNTESTABLE"


class AcceptanceCriterionResult(BaseModel):
    criterion: str
    result: CriterionResult
    notes: Optional[str] = None


class TraceabilityEntry(BaseModel):
    user_story_id: str
    feature_name: str
    status: CoverageStatus
    implementing_files: List[str] = Field(default_factory=list)
    acceptance_criteria_results: List[AcceptanceCriterionResult] = Field(default_factory=list)


class BugSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class Bug(BaseModel):
    bug_id: str
    severity: BugSeverity
    title: str
    description: str
    affected_file: str
    affected_user_story: Optional[str] = None
    reproduction_steps: List[str] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
    status: BugStatus = BugStatus.OPEN


class QARoute(str, Enum):
    DEVELOPER = "developer"
    DEVOPS_AND_DOCS = "devops_and_docs"
    HUMAN_REVIEW = "human_review"


class RoutingDecision(BaseModel):
    route_to: QARoute
    reason: str
    fix_instructions: List[Dict[str, Any]] = Field(default_factory=list)


class QAVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class QAAgentOutput(BaseModel):
    run_id: UUID
    verdict: QAVerdict
    qa_score: float = Field(..., ge=0, le=100)
    iteration: int
    traceability_matrix: List[TraceabilityEntry] = Field(default_factory=list)
    bugs: List[Bug] = Field(default_factory=list)
    routing_decision: RoutingDecision
    must_have_coverage_percent: float = Field(default=0.0, ge=0, le=100)
    critical_bugs_count: int = 0


# ════════════════════════════════════════════════════════════════════════════
# DevOps Agent
# ════════════════════════════════════════════════════════════════════════════


class DeploymentTarget(str, Enum):
    DOCKER_LOCAL = "docker-local"
    RENDER = "render"
    RAILWAY = "railway"
    VERCEL_FRONTEND_ONLY = "vercel-frontend-only"


class DevOpsAgentInput(BaseModel):
    run_id: UUID
    developer_output: DeveloperAgentOutput
    qa_output: QAAgentOutput
    deployment_target: DeploymentTarget = DeploymentTarget.DOCKER_LOCAL


class ArtifactType(str, Enum):
    DOCKERFILE = "dockerfile"
    COMPOSE = "compose"
    CI_WORKFLOW = "ci_workflow"
    ENV_TEMPLATE = "env_template"
    CONFIG = "config"


class DeploymentArtifact(BaseModel):
    path: str
    type: ArtifactType
    content: str


class EnvVariable(BaseModel):
    key: str
    description: str
    required: bool = True
    example_value: Optional[str] = None


class DevOpsAgentOutput(BaseModel):
    run_id: UUID
    deployment_artifacts: List[DeploymentArtifact] = Field(default_factory=list)
    startup_commands: List[str] = Field(default_factory=list)
    environment_variables: List[EnvVariable] = Field(default_factory=list)
    health_check_urls: List[str] = Field(default_factory=list)
    deployment_url: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# Documentation Agent
# ════════════════════════════════════════════════════════════════════════════


class DocumentationAgentInput(BaseModel):
    run_id: UUID
    research_report: ResearchReport
    prd: PRD
    design_spec: DesignSpec
    developer_output: DeveloperAgentOutput
    qa_output: QAAgentOutput
    devops_output: DevOpsAgentOutput


class DocumentationAgentOutput(BaseModel):
    run_id: UUID
    documents: Dict[str, str] = Field(
        default_factory=lambda: {
            "README.md": "",
            "API_REFERENCE.md": "",
            "ARCHITECTURE.md": "",
            "KNOWN_ISSUES.md": "",
            "CONTRIBUTING.md": "",
            "CHANGELOG.md": "",
        }
    )


# ════════════════════════════════════════════════════════════════════════════
# Schema registry — maps agent name → (input schema, output schema)
# Used by the executor to look up the right validator for each agent.
# ════════════════════════════════════════════════════════════════════════════

AGENT_SCHEMAS: Dict[str, Dict[str, type]] = {
    "orchestrator": {
        "input": OrchestratorInput,
        "output": OrchestratorOutput,
    },
    "research": {
        "input": ResearchAgentInput,
        "output": ResearchAgentOutput,
    },
    "product_manager": {
        "input": PMAgentInput,
        "output": PMAgentOutput,
    },
    "designer": {
        "input": DesignerAgentInput,
        "output": DesignerAgentOutput,
    },
    "developer": {
        "input": DeveloperAgentInput,
        "output": DeveloperAgentOutput,
    },
    "qa": {
        "input": QAAgentInput,
        "output": QAAgentOutput,
    },
    "devops": {
        "input": DevOpsAgentInput,
        "output": DevOpsAgentOutput,
    },
    "documentation": {
        "input": DocumentationAgentInput,
        "output": DocumentationAgentOutput,
    },
}
