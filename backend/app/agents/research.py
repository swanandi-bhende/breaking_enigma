"""
Research Agent - Intelligence gathering layer for market and user research.
Produces comprehensive research_report JSON used by PM Agent.
"""

from typing import Dict, Any, List, Optional
import logging
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
from app.agents.tools.search import serp_api_search


logger = logging.getLogger(__name__)


RESEARCH_SYSTEM_PROMPT = """You are a market research analyst. Your job is to gather market intelligence and produce a detailed JSON research report.

CRITICAL REQUIREMENTS:
- Respond ONLY with a valid JSON object, nothing else
- Do NOT include any markdown, code fences, or explanatory text
- Do NOT include any preamble or closing text
- All fields MUST be present in the JSON, use null only if data is truly unavailable
- Ensure ALL strings are properly escaped and quoted
- Ensure ALL arrays and objects are properly closed with correct commas

Output ONLY the JSON object, starting with { and ending with }."""


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

        schema_example = """{
  "problem_statement": {
    "core_problem": "...",
    "affected_users": "...",
    "current_solutions_fail_because": "...",
    "opportunity_window": "..."
  },
  "market": {
    "tam_usd": 0,
    "sam_usd": 0,
    "som_usd": 0,
    "industry": "...",
    "growth_rate_yoy_percent": 0,
    "key_trends": ["..."]
  },
  "personas": [
    {
      "name": "...",
      "age_range": "...",
      "occupation": "...",
      "goals": ["..."],
      "frustrations": ["..."],
      "tech_savviness": "low|medium|high",
      "primary_device": "..."
    }
  ],
  "pain_points": [
    {
      "pain": "...",
      "severity": "low|medium|high|critical",
      "frequency": "rare|occasional|frequent|constant",
      "existing_workaround": "..."
    }
  ],
  "competitors": [
    {
      "name": "...",
      "url": "...",
      "positioning": "...",
      "pricing_model": "...",
      "key_features": ["..."],
      "weaknesses": ["..."],
      "user_sentiment": "..."
    }
  ],
  "viability": {
    "revenue_models": ["..."],
    "recommended_model": "...",
    "estimated_arpu": "...",
    "go_to_market_strategy": "...",
    "viability_score": 5
  },
  "feasibility": {
    "technical_risks": ["..."],
    "complexity": "low|medium|high",
    "estimated_mvp_weeks": 0,
    "key_dependencies": ["..."],
    "feasibility_score": 5
  }
}"""

        return f"""Product Idea: {normalized_idea}
Domain: {domain}
Target Platform: {target_platform}

Conduct comprehensive market research and produce a detailed research report matching this JSON schema:

{schema_example}

Requirements:
1. Use web search to gather real data where possible
2. Fill in ALL fields - use null only if absolutely necessary
3. Ensure 2+ competitors with complete data
4. Return ONLY the JSON object, no additional text"""

    async def _collect_search_evidence(self, project_brief: Dict[str, Any]) -> Dict[str, Any]:
        """Collect live web evidence to ground the research report."""
        normalized_idea = project_brief.get("normalized_idea", "")
        domain = project_brief.get("domain", "general")

        queries = [
            f"{normalized_idea} market size TAM SAM SOM",
            f"{normalized_idea} top competitors pricing",
            f"{domain} user pain points trends 2025 2026",
        ]

        source = "serp_api" if settings.SERP_API_KEY else "web_search"
        collected_results: List[Dict[str, Any]] = []

        for query in queries:
            if source == "serp_api":
                raw_results = serp_api_search.invoke({"query": query, "num_results": 5})
            else:
                raw_results = web_search.invoke({"query": query, "num_results": 5})

            for item in raw_results:
                if isinstance(item, dict) and not item.get("error"):
                    collected_results.append(
                        {
                            "query": query,
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("snippet", ""),
                        }
                    )

        logger.info("[research] using %s evidence, records=%d", source, len(collected_results))
        return {"source": source, "results": collected_results}

    def _format_evidence_for_prompt(self, evidence: Dict[str, Any]) -> str:
        """Render concise evidence blocks for the LLM prompt."""
        source = evidence.get("source", "web_search")
        results = evidence.get("results", [])
        if not results:
            return "No external evidence found. Use conservative estimates and clearly avoid overclaiming."

        lines = [f"Source provider: {source}"]
        for idx, row in enumerate(results[:12], start=1):
            lines.append(
                f"{idx}. Query: {row.get('query', '')}\n"
                f"   Title: {row.get('title', '')}\n"
                f"   URL: {row.get('url', '')}\n"
                f"   Snippet: {row.get('snippet', '')}"
            )
        return "\n".join(lines)

    async def run(self, input_data: ResearchAgentInput | Dict[str, Any]) -> ResearchAgentOutput:
        """Execute the Research Agent with exponential backoff for rate limits."""
        import asyncio
        import json
        
        if isinstance(input_data, dict):
            input_data = ResearchAgentInput.model_validate(input_data)

        run_id = input_data.run_id
        project_brief = input_data.project_brief

        prompt = self._build_research_prompt(project_brief)
        evidence = await self._collect_search_evidence(project_brief)
        evidence_block = self._format_evidence_for_prompt(evidence)
        prompt = (
            prompt
            + "\n\nUse this evidence for estimates and competitor analysis:\n"
            + evidence_block
        )

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.llm.ainvoke(
                    [
                        ("system", RESEARCH_SYSTEM_PROMPT),
                        ("human", prompt),
                    ]
                )
                
                # Extract and parse JSON with multiple fallback strategies
                response_content = response.content
                logger.info(f"[research] Raw response length: {len(response_content)} chars")
                
                json_obj = None
                
                # Strategy 1: Try extract_json_from_response
                try:
                    json_obj = extract_json_from_response(response_content)
                    logger.info(f"[research] Successfully parsed JSON using extract_json_from_response")
                except Exception as e1:
                    logger.warning(f"[research] extract_json_from_response failed: {str(e1)[:100]}")
                    
                    # Strategy 2: Try direct JSON parsing
                    try:
                        json_obj = json.loads(response_content.strip())
                        logger.info(f"[research] Successfully parsed JSON using direct parsing")
                    except Exception as e2:
                        logger.warning(f"[research] Direct JSON parsing failed: {str(e2)[:100]}")
                        
                        # Strategy 3: Find and extract JSON object
                        try:
                            import re
                            # Find the first { and last } to extract potential JSON
                            start_idx = response_content.find('{')
                            end_idx = response_content.rfind('}')
                            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                                potential_json = response_content[start_idx:end_idx+1]
                                json_obj = json.loads(potential_json)
                                logger.info(f"[research] Successfully parsed JSON using bracket extraction")
                            else:
                                raise ValueError("Could not find JSON brackets in response")
                        except Exception as e3:
                            logger.error(f"[research] Bracket extraction failed: {str(e3)[:100]}")
                            raise ValueError(f"Could not parse JSON from response after all strategies: {e1}")
                
                if json_obj is None:
                    raise ValueError("JSON parsing returned None")
                
                # Validate required fields
                required_fields = ["problem_statement", "market", "personas", "pain_points", "competitors", "viability", "feasibility"]
                missing_fields = [f for f in required_fields if f not in json_obj]
                if missing_fields:
                    raise ValueError(f"Missing required fields in JSON: {missing_fields}")
                
                # Validate competitors
                competitors = json_obj.get("competitors", [])
                if len(competitors) < 2:
                    raise ValueError(f"Need at least 2 complete competitors, got {len(competitors)}")
                
                # Construct ResearchReport with validation
                logger.info(f"[research] JSON validation passed, creating ResearchReport")
                try:
                    result = ResearchReport(**json_obj)
                except Exception as validation_error:
                    logger.error(f"[research] Pydantic validation error: {str(validation_error)[:500]}")
                    # Log the failing fields for debugging
                    error_str = str(validation_error)
                    logger.error(f"[research] Full JSON keys: {list(json_obj.keys())}")
                    raise
                    
                research_report_dict = result.dict()

                embedding_ids = await self._store_embeddings(
                    run_id, research_report_dict
                )

                return ResearchAgentOutput(
                    run_id=run_id, research_report=result, embedding_ids=embedding_ids
                )

            except Exception as e:
                error_str = str(e)
                last_error = e
                logger.error(f"[research] Attempt {attempt+1}/{self.max_retries} failed: {error_str[:200]}")
                
                # Handle rate limit with exponential backoff
                if "rate_limit_exceeded" in error_str or "429" in error_str:
                    wait_time = min(2 ** attempt * 10, 120)  # Exponential backoff
                    logger.warning(f"[research] Rate limit, waiting {wait_time}s before retry {attempt+1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                
                # Retry on parsing errors
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
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
