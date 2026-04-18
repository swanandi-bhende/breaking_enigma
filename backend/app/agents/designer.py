"""
Designer Agent — Architectural and visual design engine.
Produces complete design_spec with screens, API spec, and data models.
Uses RAG to retrieve relevant research context from Qdrant.

Entry-point: run_designer_agent(input_dict: dict) -> dict
"""

import logging
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.core.llm import llm_client
from app.core.qdrant import qdrant_manager
from app.schemas.designer import (
    DesignerAgentInput,
    DesignerAgentOutput,
    DesignSpec,
    ArchitectureOutput,
    DatabaseSchemaOutput,
    UIWireframesOutput,
    UXFlowOutput,
)
from app.schemas.research_pm import PRD

logger = logging.getLogger(__name__)

COMMON_PROMPT_PREFIX = """You are the Designer Agent in an autonomous product development system.
Your role is to produce a design specification slice based on the PRD context provided."""

ARCH_SYSTEM_PROMPT = COMMON_PROMPT_PREFIX + """
## Task: System Architecture & APIs
Produce the System Architecture and API Specifications ONLY.
Map every API endpoint to specific user stories.
{format_instructions}
"""

DB_SYSTEM_PROMPT = COMMON_PROMPT_PREFIX + """
## Task: Database Schema
Produce the Data Models ONLY based on the context and architecture.
Design complete data models with proper relationships (one-to-one, one-to-many, many-to-many, many-to-one).
{format_instructions}
"""

UI_SYSTEM_PROMPT = COMMON_PROMPT_PREFIX + """
## Task: UI Wireframes & Screens
Produce the Screen specifications ONLY. Define every screen, purpose, components, wireframe descriptions, UX decisions, and edge cases.
{format_instructions}
"""

UX_SYSTEM_PROMPT = COMMON_PROMPT_PREFIX + """
## Task: Interaction Flows
Produce the UX Flow specifications ONLY. Define trigger, steps, happy paths, and failure paths.
{format_instructions}
"""


class DesignerAgent:
    """Designer Agent for design specification generation."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        self.parsers = {
            "arch": PydanticOutputParser(pydantic_object=ArchitectureOutput),
            "db": PydanticOutputParser(pydantic_object=DatabaseSchemaOutput),
            "ui": PydanticOutputParser(pydantic_object=UIWireframesOutput),
            "ux": PydanticOutputParser(pydantic_object=UXFlowOutput),
        }
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
                query=query, query_vector=query_vector, run_id=str(run_id), limit=5
            )
            return [r["text"] for r in results]
        except Exception as e:
            logger.warning(f"Failed to retrieve research context: {e}")
            return []

    def _build_context_string(self, prd: PRD, research_context: List[str], extra_context: str = "") -> str:
        prd_dict = prd.model_dump()
        product_vision = prd_dict.get("product_vision", {})
        user_stories = prd_dict.get("user_stories", [])
        features = prd_dict.get("features", {})
        user_flow = prd_dict.get("user_flow", [])

        context = f"## Product Vision:\n{product_vision.get('core_value_proposition', '')}\n\n"
        
        if research_context:
            context += "## Research Context (from RAG):\n" + "\n".join([f"- {ctx}" for ctx in research_context[:3]]) + "\n\n"
            
        if user_stories:
            context += "## User Stories:\n" + "\n".join([f"- {us.get('id', f'US-{i:03d}')}: {us.get('action', '')}" for i, us in enumerate(user_stories[:10])]) + "\n\n"
            
        if features:
            mvp_features = features.get("mvp", [])
            context += "## MVP Features:\n" + "\n".join([f"- {f.get('name', '')}: {f.get('description', '')}" for f in mvp_features[:5]]) + "\n\n"
            
        if user_flow:
            context += "## Base User Flow:\n" + "\n".join([f"Step {step.get('step', i+1)}: {step.get('screen_name', '')}" for i, step in enumerate(user_flow)]) + "\n\n"

        if extra_context:
            context += f"## Previous Agent Context:\n{extra_context}\n\n"
            
        return context

    async def _execute_step(self, run_id: str, step_name: str, system_prompt: str, context: str, parser_key: str):
        parser = self.parsers[parser_key]
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                try:
                    from app.core.redis import publish_log_line
                    await publish_log_line(run_id, "designer", f"Generating {step_name} (attempt {attempt + 1})...")
                except Exception:
                    pass

                chain = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{input}")]) | self.llm | parser
                result = await chain.ainvoke({
                    "input": context,
                    "format_instructions": parser.get_format_instructions()
                })
                
                try:
                    from app.core.redis import publish_log_line
                    await publish_log_line(run_id, "designer", f"{step_name} generation complete ✓")
                except Exception:
                    pass
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Designer step {step_name} attempt {attempt + 1} failed: {e}")
                
        raise Exception(f"Designer step {step_name} failed after {self.max_retries} attempts: {last_error}")

    async def run(self, input_data: DesignerAgentInput) -> DesignerAgentOutput:
        run_id = str(input_data.run_id)
        prd_data = input_data.prd
        embedding_ids = input_data.research_context_embedding_ids

        try:
            from app.core.redis import publish_log_line
            await publish_log_line(run_id, "designer", "Designing system sequentially to respect token limits...")
        except Exception:
            pass

        prd = PRD.model_validate(prd_data) if isinstance(prd_data, dict) else prd_data
        research_context = await self._retrieve_research_context(run_id, embedding_ids)

        # 1. Arch
        arch_res = await self._execute_step(
            run_id, "Architecture & APIs", ARCH_SYSTEM_PROMPT, 
            self._build_context_string(prd, research_context), "arch"
        )
        
        # 2. DB (pass arch context)
        arch_context = f"Architecture: Backend={arch_res.system_architecture.backend}, DB={arch_res.system_architecture.database}\nAPIs: {[ep.path for ep in arch_res.api_spec]}"
        db_res = await self._execute_step(
            run_id, "Database Schema", DB_SYSTEM_PROMPT, 
            self._build_context_string(prd, research_context, arch_context), "db"
        )
        
        # 3. UI
        ui_res = await self._execute_step(
            run_id, "UI Screens", UI_SYSTEM_PROMPT, 
            self._build_context_string(prd, research_context), "ui"
        )
        
        # 4. UX
        ui_context = f"Screens: {[s.screen_name for s in ui_res.screens]}"
        ux_res = await self._execute_step(
            run_id, "UX Flows", UX_SYSTEM_PROMPT, 
            self._build_context_string(prd, research_context, ui_context), "ux"
        )

        final_spec = DesignSpec(
            screens=ui_res.screens,
            interaction_flows=ux_res.interaction_flows,
            system_architecture=arch_res.system_architecture,
            api_spec=arch_res.api_spec,
            data_models=db_res.data_models
        )

        return DesignerAgentOutput(run_id=run_id, design_spec=final_spec)


async def run_designer_agent(input_dict: dict) -> dict:
    """
    Main entry-point for Designer Agent.
    Accepts a plain dict (from executor), returns a plain dict.
    """
    input_data = DesignerAgentInput.model_validate(input_dict)
    agent = DesignerAgent()
    result = await agent.run(input_data)
    return result.model_dump(mode="json")
