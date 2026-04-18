"""
Designer Agent - Architectural and visual design engine.
Produces complete design_spec with screens, API spec, and data models.
Uses RAG to retrieve relevant research context from Qdrant.
"""

from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ...core.config import settings
from ...core.llm import llm_client
from ...core.qdrant import qdrant_manager
from ...schemas.designer import (
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
from ...schemas.research_pm import PRD


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
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
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

    async def run(self, input_data: DesignerAgentInput) -> DesignerAgentOutput:
        """
        Execute the Designer Agent.

        Args:
            input_data: DesignerAgentInput with run_id, prd, and research_context_embedding_ids

        Returns:
            DesignerAgentOutput with complete design_spec
        """
        run_id = input_data.run_id
        prd_data = input_data.prd
        embedding_ids = input_data.research_context_embedding_ids

        prd = PRD(**prd_data) if isinstance(prd_data, dict) else prd_data

        research_context = await self._retrieve_research_context(run_id, embedding_ids)

        prompt = self._build_design_prompt(prd, research_context)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                chain = (
                    ChatPromptTemplate.from_messages(
                        [("system", DESIGNER_SYSTEM_PROMPT), ("human", "{input}")]
                    )
                    | self.llm
                    | self.parser
                )

                result = await chain.ainvoke({"input": prompt})

                return DesignerAgentOutput(run_id=run_id, design_spec=result)

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    continue

        raise Exception(
            f"Designer Agent failed after {self.max_retries} attempts: {last_error}"
        )


async def run_designer_agent(input_data: DesignerAgentInput) -> DesignerAgentOutput:
    """Main entry point for Designer Agent."""
    agent = DesignerAgent()
    return await agent.run(input_data)
