"""
Research Agent - Intelligence gathering layer for market and user research.
Produces comprehensive research_report JSON used by PM Agent.
"""

from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import json

from app.core.config import settings
from app.core.llm import llm_client
from app.core.qdrant import qdrant_manager
from app.schemas.research_pm import (
    ResearchAgentInput,
    ResearchAgentOutput,
    ResearchReport,
    ProblemStatement,
    MarketData,
    Persona,
    PainPoint,
    Competitor,
    ViabilityData,
    FeasibilityData,
)
from app.utils.chunking import chunk_text_by_tokens, extract_json_from_response
from app.utils.chunking import format_research_for_embedding
from app.agents.tools.search import web_search, get_available_tools


RESEARCH_SYSTEM_PROMPT = """You are the Research Agent in an autonomous product development system.
Your role is to gather comprehensive market and user intelligence for a product idea.

## Your Responsibilities:
1. **Problem Clarification** - Decompose the idea into clear problem statement, user hypothesis, solution hypothesis
2. **Market Research** - TAM/SAM/SOM estimation, industry overview, growth trends, market timing
3. **User Research** - Persona creation (3-5 archetypes), target segment definition
4. **Pain Point Extraction** - Ranked list of user pains mapped to existing solutions
5. **Competitor Analysis** - Top 5 competitors: features, pricing, positioning, weaknesses
6. **Business Viability** - Revenue model options, monetization potential
7. **Technical Feasibility** - Tech risk assessment, key technical challenges

## Output Requirements:
- You MUST respond with ONLY a valid JSON object matching the schema below
- Do NOT include any explanatory text, markdown code fences, or preamble
- If you cannot complete a field, use null — never omit required fields
- Use realistic estimates when exact data is unavailable

## Research Report Schema:
```json
{
  "problem_statement": {
    "core_problem": "string",
    "affected_users": "string", 
    "current_solutions_fail_because": "string",
    "opportunity_window": "string"
  },
  "market": {
    "tam_usd": 0,
    "sam_usd": 0,
    "som_usd": 0,
    "industry": "string",
    "growth_rate_yoy_percent": 0,
    "key_trends": ["string"]
  },
  "personas": [
    {
      "name": "string",
      "age_range": "string",
      "occupation": "string",
      "goals": ["string"],
      "frustrations": ["string"],
      "tech_savviness": "low|medium|high",
      "primary_device": "string"
    }
  ],
  "pain_points": [
    {
      "pain": "string",
      "severity": "low|medium|high|critical",
      "frequency": "rare|occasional|frequent|constant",
      "existing_workaround": "string"
    }
  ],
  "competitors": [
    {
      "name": "string",
      "url": "string",
      "positioning": "string",
      "pricing_model": "string",
      "key_features": ["string"],
      "weaknesses": ["string"],
      "user_sentiment": "string"
    }
  ],
  "viability": {
    "revenue_models": ["string"],
    "recommended_model": "string",
    "estimated_arpu": "string",
    "go_to_market_strategy": "string",
    "viability_score": 1-10
  },
  "feasibility": {
    "technical_risks": ["string"],
    "complexity": "low|medium|high",
    "estimated_mvp_weeks": 0,
    "key_dependencies": ["string"],
    "feasibility_score": 1-10
  }
}
```

## Tool Usage:
You have access to web search tools. Use them to gather real data for:
- Market size estimates
- Competitor information
- Industry trends
- User pain points

Be thorough but pragmatic. Return your complete research report as a JSON object."""


class ResearchAgent:
    """Research Agent for comprehensive market and user intelligence."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        self.parser = PydanticOutputParser(pydantic_object=ResearchReport)
        self.max_retries = 3

    def _build_research_prompt(self, project_brief: Dict[str, Any]) -> str:
        """Build the research prompt from project brief."""
        normalized_idea = project_brief.get("normalized_idea", "")
        domain = project_brief.get("domain", "general")
        target_platform = project_brief.get("target_platform", "web")

        return f"""Product Idea: {normalized_idea}
Domain: {domain}
Target Platform: {target_platform}

Based on this product idea, conduct comprehensive research and produce a detailed research report in JSON format.

Use web search to gather real market data, competitor information, and industry trends.
Focus on realistic estimates and actionable insights.

{self.parser.get_format_instructions()}"""

    async def run(self, input_data: ResearchAgentInput | Dict[str, Any]) -> ResearchAgentOutput:
        """
        Execute the Research Agent.

        Args:
            input_data: ResearchAgentInput with run_id and project_brief

        Returns:
            ResearchAgentOutput with complete research_report
        """
        if isinstance(input_data, dict):
            input_data = ResearchAgentInput.model_validate(input_data)

        run_id = input_data.run_id
        project_brief = input_data.project_brief

        prompt = self._build_research_prompt(project_brief)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.llm.ainvoke(
                    [
                        ("system", RESEARCH_SYSTEM_PROMPT),
                        ("human", prompt),
                    ]
                )
                result = self.parser.parse(response.content)

                research_report_dict = result.dict()

                embedding_ids = await self._store_embeddings(
                    run_id, research_report_dict
                )

                return ResearchAgentOutput(
                    run_id=run_id, research_report=result, embedding_ids=embedding_ids
                )

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    continue

        raise Exception(
            f"Research Agent failed after {self.max_retries} attempts: {last_error}"
        )

    async def _store_embeddings(
        self, run_id: str, research_report: Dict[str, Any]
    ) -> List[str]:
        """Store research report chunks in Qdrant for RAG."""
        try:
            sections = format_research_for_embedding(research_report)

            if not sections:
                return []

            chunks = []
            for section in sections:
                section_chunks = chunk_text_by_tokens(
                    section, chunk_size=800, overlap=50
                )
                chunks.extend(section_chunks)

            vectors = await llm_client.embed_texts(chunks)

            embedding_ids = await qdrant_manager.store_research_embeddings(
                run_id=run_id, chunks=chunks, vectors=vectors
            )

            return embedding_ids

        except Exception as e:
            print(f"Warning: Failed to store embeddings: {e}")
            return []

    async def search_and_analyze(self, query: str) -> List[Dict[str, str]]:
        """Use web search for additional research."""
        try:
            result = web_search.invoke({"query": query, "num_results": 5})
            return result
        except Exception as e:
            return [{"error": str(e)}]


async def run_research_agent(input_data: ResearchAgentInput | Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point for Research Agent.

    The workflow executor validates raw dictionaries, so return serialized
    output rather than a pydantic model instance.
    """
    agent = ResearchAgent()
    result = await agent.run(input_data)
    return result.model_dump(mode="json")
