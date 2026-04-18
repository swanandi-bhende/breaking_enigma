"""
Designer Agent - Architectural and visual design engine.
Produces complete design_spec with screens, API spec, and data models.
Uses RAG to retrieve relevant research context from Qdrant.
"""

import re
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.core.llm import llm_client
from app.core.qdrant import qdrant_manager
from app.schemas.designer import (
    DesignerAgentInput,
    DesignerAgentOutput,
    DesignSpec,
    Screen,
    Component,
    InteractionFlow,
    SystemArchitecture,
    APIEndpoint,
    RequestBodySchema,
    ResponseSchemaItem,
    DataModel,
    DataModelField,
    Relationship,
)
from app.schemas.research_pm import PRD


def _slugify(value: str) -> str:
  slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
  return slug or "product"


def _safe_text(value: Any, fallback: str = "-") -> str:
  if value is None:
    return fallback
  text = str(value).strip()
  return text if text else fallback


def _build_component(name: str, component_type: str, props: Optional[Dict[str, Any]] = None, dependencies: Optional[List[str]] = None) -> Dict[str, Any]:
  return {
    "component_name": name,
    "type": component_type,
    "props": props or {},
    "state_dependencies": dependencies or [],
  }


def _build_screen(screen_id: str, screen_name: str, route: str, purpose: str, components: List[Dict[str, Any]], ux_decisions: List[str], edge_cases: List[str], wireframe_description: str) -> Dict[str, Any]:
  return {
    "screen_id": screen_id,
    "screen_name": screen_name,
    "route": route,
    "purpose": purpose,
    "components": components,
    "ux_decisions": ux_decisions,
    "edge_cases": edge_cases,
    "wireframe_description": wireframe_description,
  }


def _build_endpoint(endpoint_id: str, method: str, path: str, description: str, maps_to_user_stories: List[str], auth_required: bool = False) -> Dict[str, Any]:
  return {
    "endpoint_id": endpoint_id,
    "method": method,
    "path": path,
    "auth_required": auth_required,
    "description": description,
    "request_body": {
      "content_type": "application/json",
      "schema_def": {},
      "validation_rules": ["Validate required fields", "Return a structured validation error on failure"],
    },
    "responses": {
      "200": {
        "description": "Successful response",
        "schema_def": {},
        "example": {},
      }
    },
    "rate_limit": "60 requests/minute",
    "maps_to_user_stories": maps_to_user_stories,
  }


def _build_data_model(entity_name: str, table_name: str, fields: List[Dict[str, Any]], relationships: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
  return {
    "entity_name": entity_name,
    "table_name": table_name,
    "fields": fields,
    "relationships": relationships or [],
  }


def _screen_components_for_step(step_name: str, is_primary: bool) -> List[Dict[str, Any]]:
  return [
    _build_component("top-nav", "navigation", {"style": "sticky"}, ["app.user"]),
    _build_component("hero-summary", "display", {"variant": "summary", "title": step_name}, ["page.state"]),
    _build_component(
      "primary-action",
      "form" if is_primary else "display",
      {"intent": "primary"},
      ["page.state", "form.errors"],
    ),
    _build_component("status-feedback", "feedback", {"style": "inline"}, ["page.loading", "page.error"]),
  ]


def _build_design_spec_from_prd(prd: PRD) -> Dict[str, Any]:
  project_name = _safe_text(prd.product_vision.elevator_pitch, "Product Experience")
  project_slug = _slugify(project_name)

  user_stories = list(prd.user_stories or [])
  user_flow = list(prd.user_flow or [])
  mvp_features = list(prd.features.mvp or [])
  v11_features = list(prd.features.v1_1 or [])
  v20_features = list(prd.features.v2_0 or [])

  screens: List[Dict[str, Any]] = []
  if user_flow:
    for index, flow_step in enumerate(user_flow[:5]):
      step_slug = _slugify(flow_step.screen_name)
      screens.append(
        _build_screen(
          screen_id=f"screen-{step_slug}",
          screen_name=flow_step.screen_name,
          route="/" if index == 0 else f"/{step_slug}",
          purpose=f"Support step {flow_step.step}: {flow_step.user_action}",
          components=_screen_components_for_step(flow_step.screen_name, index == 0),
          ux_decisions=[
            "Keep the primary action visible above the fold",
            "Use progressive disclosure for secondary details",
            "Show inline validation and status feedback",
          ],
          edge_cases=[
            "Loading state while data is fetched",
            "Validation errors on submission",
            "Empty state when there is no saved data",
          ],
          wireframe_description=(
            f"Header with navigation, a focused content card for {flow_step.screen_name}, "
            f"primary action area, and a feedback strip for success or error states."
          ),
        )
      )
  else:
    screens.append(
      _build_screen(
        screen_id="screen-home",
        screen_name="Home",
        route="/",
        purpose="Introduce the experience and guide the user into the primary workflow.",
        components=_screen_components_for_step(project_name, True),
        ux_decisions=[
          "Keep onboarding lightweight",
          "Highlight the single primary call to action",
          "Use a clean mobile-first layout",
        ],
        edge_cases=["No data available", "API load failure", "User has not completed onboarding"],
        wireframe_description="Top navigation, hero summary block, action cards, and a compact feedback banner.",
      )
    )

  if mvp_features:
    primary_feature = mvp_features[0]
    screens.append(
      _build_screen(
        screen_id=f"screen-{_slugify(primary_feature.name)}",
        screen_name=primary_feature.name,
        route=f"/{_slugify(primary_feature.name)}",
        purpose=primary_feature.description,
        components=[
          _build_component("section-header", "layout", {"title": primary_feature.name}, ["feature.state"]),
          _build_component("feature-card-grid", "display", {"cards": "primary"}, ["feature.items"]),
          _build_component("primary-cta", "form", {"label": "Continue"}, ["feature.form"]),
        ],
        ux_decisions=["Prioritize task completion over decorative elements", "Keep actions one click away"],
        edge_cases=["No items returned", "User input is incomplete"],
        wireframe_description=f"Section header followed by a structured feature card grid for {primary_feature.name}.",
      )
    )

  interaction_steps = [
    f"Step {step.step}: {step.screen_name} - {step.user_action}"
    for step in user_flow[:5]
  ] or [
    "Open the home screen",
    "Review the primary action area",
    "Submit or continue the workflow",
    "Confirm success and surface the next best action",
  ]

  api_spec = [
    _build_endpoint(
      endpoint_id="api-projects-list",
      method="GET",
      path="/api/v1/projects",
      description="List all saved projects for the current user.",
      maps_to_user_stories=[story.id for story in user_stories[:2]],
      auth_required=True,
    ),
    _build_endpoint(
      endpoint_id="api-projects-create",
      method="POST",
      path="/api/v1/projects",
      description="Create a new project from the primary workflow.",
      maps_to_user_stories=[story.id for story in user_stories[:3]],
      auth_required=True,
    ),
    _build_endpoint(
      endpoint_id="api-projects-detail",
      method="GET",
      path="/api/v1/projects/{project_id}",
      description="Return project details, state, and related items.",
      maps_to_user_stories=[story.id for story in user_stories[:3]],
      auth_required=True,
    ),
  ]

  if v11_features:
    api_spec.append(
      _build_endpoint(
        endpoint_id="api-projects-update",
        method="PATCH",
        path="/api/v1/projects/{project_id}",
        description="Update a project draft or saved configuration.",
        maps_to_user_stories=[story.id for story in user_stories[1:4]],
        auth_required=True,
      )
    )

  if v20_features:
    api_spec.append(
      _build_endpoint(
        endpoint_id="api-projects-archive",
        method="DELETE",
        path="/api/v1/projects/{project_id}",
        description="Archive or remove a completed project.",
        maps_to_user_stories=[story.id for story in user_stories[-2:]],
        auth_required=True,
      )
    )

  data_models = [
    _build_data_model(
      "User",
      "users",
      [
        {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
        {"name": "email", "type": "text", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
        {"name": "name", "type": "text", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": None},
        {"name": "created_at", "type": "datetime", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "now()"},
      ],
      [{"type": "one-to-many", "with_entity": "Project", "foreign_key": "user_id"}],
    ),
    _build_data_model(
      "Project",
      "projects",
      [
        {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
        {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
        {"name": "title", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
        {"name": "status", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "draft"},
        {"name": "created_at", "type": "datetime", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "now()"},
      ],
      [
        {"type": "one-to-many", "with_entity": "Task", "foreign_key": "project_id"},
      ],
    ),
    _build_data_model(
      "Task",
      "tasks",
      [
        {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
        {"name": "project_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "projects.id", "default": None},
        {"name": "title", "type": "text", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": None},
        {"name": "description", "type": "text", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
        {"name": "status", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "todo"},
        {"name": "priority", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "medium"},
      ],
      [],
    ),
  ]

  design_spec = DesignSpec(
    screens=screens,
    interaction_flows=[
      InteractionFlow(
        flow_id="flow-primary",
        flow_name=f"Primary workflow for {project_name}",
        trigger="User opens the product and starts the main task",
        steps=interaction_steps,
        happy_path_end="User completes the core task and sees a confirmation state",
        failure_paths=["Validation error", "Network timeout", "Empty results state"],
      ),
      InteractionFlow(
        flow_id="flow-recovery",
        flow_name="Error and recovery flow",
        trigger="An action fails or returns incomplete data",
        steps=[
          "Show inline error feedback",
          "Preserve user input",
          "Offer retry and back navigation",
        ],
        happy_path_end="User retries successfully and resumes the main workflow",
        failure_paths=["Repeated API failure", "Invalid input format"],
      ),
    ],
    system_architecture=SystemArchitecture(
      frontend="Next.js client with reusable screen components and document-style previews",
      backend="FastAPI service orchestrating agents and product APIs",
      database="PostgreSQL for durable application data and workflow state",
      cache="Redis for events, queues, and short-lived state",
      external_services=["Qdrant for retrieval context", "LLM provider configured in environment"],
      communication_patterns={
        "client_to_api": "REST/JSON",
        "realtime_updates": "WebSocket events for pipeline and live state",
        "background_jobs": "Celery workers with Redis broker",
      },
    ),
    api_spec=api_spec,
    data_models=data_models,
  )

  return design_spec.model_dump(mode="json")


DESIGNER_SYSTEM_PROMPT = """You are the Designer Agent in an autonomous product development system.
Your role is to produce a complete design specification from the PRD: UI/UX wireframes, system architecture, API contracts, and data models.

## Your Responsibilities:

### UI/UX Design:
- Screen-level breakdown (every screen, purpose, components)
- Wireframe descriptions (text-based structured format)
- Component hierarchy (Navbar, Cards, Forms, Modals per screen)
- UX decision log (navigation style, interaction patterns)

### Interaction Flow Design:
- Step-by-step interaction for every primary user journey
- State transition map (loading, error, empty, success, auth)
- Edge case catalog

### System Architecture Design:
- High-level architecture (frontend, backend, DB, cache, external services)
- Service boundary definitions
- Communication flow (REST vs WebSocket vs SSE)

### API Specification:
- Full endpoint definitions (method, path, auth, request/response, errors)
- Authentication method and token flow
- Rate limiting rules

### Data Model Design:
- All entities with fields and types
- Relationships (FK, many-to-many)
- Indexing strategy

## Input Context:
You will receive the PRD and optionally research context retrieved via RAG.
Use the research context to inform design decisions.

## Output Requirements:
- You MUST respond with ONLY a valid JSON object matching the schema below
- Do NOT include any explanatory text, markdown code fences, or preamble
- Map every API endpoint to specific user stories
- Design complete data models with proper relationships

## Design Spec Schema:
```json
{
  "screens": [
    {
      "screen_id": "string",
      "screen_name": "string",
      "route": "string",
      "purpose": "string",
      "components": [
        {
          "component_name": "string",
          "type": "layout|form|display|navigation|feedback",
          "props": {},
          "state_dependencies": ["string"]
        }
      ],
      "ux_decisions": ["string"],
      "edge_cases": ["string"],
      "wireframe_description": "string"
    }
  ],
  "interaction_flows": [
    {
      "flow_id": "string",
      "flow_name": "string",
      "trigger": "string",
      "steps": ["string"],
      "happy_path_end": "string",
      "failure_paths": ["string"]
    }
  ],
  "system_architecture": {
    "frontend": "string",
    "backend": "string",
    "database": "string",
    "cache": "string",
    "external_services": ["string"],
    "communication_patterns": {}
  },
  "api_spec": [
    {
      "endpoint_id": "string",
      "method": "GET|POST|PUT|PATCH|DELETE",
      "path": "string",
      "auth_required": true|false,
      "description": "string",
      "request_body": {
        "content_type": "string",
        "request_schema": {},
        "validation_rules": ["string"]
      },
      "responses": {
        "200": {"description": "string", "response_schema": {}, "example": {}}
      },
      "rate_limit": "string",
      "maps_to_user_stories": ["US-001"]
    }
  ],
  "data_models": [
    {
      "entity_name": "string",
      "table_name": "string",
      "fields": [
        {
          "name": "string",
          "type": "string",
          "nullable": true|false,
          "unique": true|false,
          "indexed": true|false,
          "foreign_key": "string|null",
          "default": "string|null"
        }
      ],
      "relationships": [
        {
          "type": "one-to-one|one-to-many|many-to-many",
          "with_entity": "string",
          "foreign_key": "string"
        }
      ]
    }
  ]
}
```

Return your complete design specification as a JSON object."""


class DesignerAgent:
    """Designer Agent for design specification generation."""

    def __init__(self):
        api_key = settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
        base_url = settings.GEMINI_BASE_URL if settings.GEMINI_API_KEY else settings.OPENAI_BASE_URL
        model = settings.GEMINI_MODEL if settings.GEMINI_API_KEY else settings.OPENAI_MODEL

        self.llm = ChatOpenAI(
            model=model,
            temperature=0.3,
            api_key=api_key,
            base_url=base_url,
        )
        self.parser = PydanticOutputParser(pydantic_object=DesignSpec)
        self.max_retries = 3

    async def _retrieve_research_context(
        self,
        run_id: str,
        embedding_ids: List[str],
        query: str = "user authentication pain points features design requirements",
    ) -> List[str]:
        """Retrieve relevant research context from Qdrant for RAG."""
        try:
            if not embedding_ids:
                return []

            query_vector = await llm_client.embed_query(query)

            results = await qdrant_manager.retrieve_research_context(
                query=query, query_vector=query_vector, run_id=run_id, limit=5
            )

            return [r["text"] for r in results]
        except Exception as e:
            print(f"Warning: Failed to retrieve research context: {e}")
            return []

    def _build_design_prompt(self, prd: PRD, research_context: List[str]) -> str:
        """Build the design prompt from PRD and research context."""
        prd_dict = prd.dict()

        product_vision = prd_dict.get("product_vision", {})
        user_stories = prd_dict.get("user_stories", [])
        features = prd_dict.get("features", {})
        user_flow = prd_dict.get("user_flow", [])

        context_section = ""
        if research_context:
            context_section = f"""
## Research Context (from RAG):
{chr(10).join([f"- {ctx}" for ctx in research_context[:3]])}

Use this context to inform your design decisions.
"""

        stories_section = ""
        if user_stories:
            stories_section = f"""
## User Stories (for API mapping):
{
                chr(10).join(
                    [
                        f"- {us.get('id', f'US-{i:03d}')}: {us.get('action', '')} so that {us.get('outcome', '')}"
                        for i, us in enumerate(user_stories[:10])
                    ]
                )
            }

Map each API endpoint to at least one user story.
"""

        features_section = ""
        if features:
            mvp_features = features.get("mvp", [])
            features_section = f"""
## MVP Features (must implement):
{chr(10).join([f"- {f.get('name', '')}: {f.get('description', '')}" for f in mvp_features[:5]])}

Design screens and APIs to support these features.
"""

        user_flow_section = ""
        if user_flow:
            user_flow_section = f"""
## User Flow:
{
                chr(10).join(
                    [
                        f"Step {step.get('step', i + 1)}: {step.get('screen_name', '')} - {step.get('user_action', '')}"
                        for i, step in enumerate(user_flow)
                    ]
                )
            }
"""

        prompt = f"""{context_section}

## Product Vision:
{product_vision.get("core_value_proposition", "")}

{stories_section}
{features_section}
{user_flow_section}

Now create the complete design specification.
{self.parser.get_format_instructions()}"""

        return prompt

    async def run(self, input_data: DesignerAgentInput | Dict[str, Any]) -> DesignerAgentOutput:
        """
        Execute the Designer Agent.

        Args:
            input_data: DesignerAgentInput with run_id, prd, and research_context_embedding_ids

        Returns:
            DesignerAgentOutput with complete design_spec
        """
        if isinstance(input_data, dict):
          input_data = DesignerAgentInput.model_validate(input_data)

        run_id = input_data.run_id
        prd_data = input_data.prd
        embedding_ids = input_data.research_context_embedding_ids

        prd = PRD(**prd_data) if isinstance(prd_data, dict) else prd_data

        research_context = await self._retrieve_research_context(run_id, embedding_ids)

        prompt = self._build_design_prompt(prd, research_context)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.llm.ainvoke(
                    [
                        ("system", DESIGNER_SYSTEM_PROMPT),
                        ("human", prompt),
                    ]
                )
                result = self.parser.parse(response.content)

                return DesignerAgentOutput(run_id=run_id, design_spec=result)

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    continue

        raise Exception(
            f"Designer Agent failed after {self.max_retries} attempts: {last_error}"
        )


async def run_designer_agent(input_data: DesignerAgentInput | Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point for Designer Agent.

    The design spec is derived from the PRD so the UI can render a readable
    document while downstream agents still receive structured JSON.
    """
    if isinstance(input_data, dict):
        input_data = DesignerAgentInput.model_validate(input_data)

    run_id = str(input_data.run_id)
    prd = input_data.prd if isinstance(input_data.prd, PRD) else PRD.model_validate(input_data.prd)

    design_spec = _build_design_spec_from_prd(prd)

    return {
        "run_id": run_id,
        "design_spec": design_spec,
    }
