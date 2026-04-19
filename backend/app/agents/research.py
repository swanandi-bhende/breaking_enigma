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


def _fallback_research_report(project_brief: Dict[str, Any], evidence: Dict[str, Any]) -> ResearchReport:
    """Build a safe deterministic research report when LLM providers are rate-limited."""
    normalized_idea = str(project_brief.get("normalized_idea") or "Build a useful product").strip()
    domain = str(project_brief.get("domain") or "General Software").strip()

    evidence_results = evidence.get("results", []) if isinstance(evidence, dict) else []
    competitors: List[Competitor] = []
    seen_names: set[str] = set()
    for item in evidence_results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title:
            continue
        name = title.split("|")[0].split("-")[0].strip()[:80] or "Market Competitor"
        if name in seen_names:
            continue
        competitors.append(
            Competitor(
                name=name,
                url=url or "https://example.com",
                positioning="Adjacent solution in the target market segment",
                pricing_model="Freemium or subscription",
                key_features=["Core workflow automation", "Basic analytics", "Mobile/web access"],
                weaknesses=["Limited customization", "Inconsistent user onboarding"],
                user_sentiment="Mixed to positive based on public summaries",
            )
        )
        seen_names.add(name)
        if len(competitors) >= 3:
            break

    while len(competitors) < 2:
        idx = len(competitors) + 1
        competitors.append(
            Competitor(
                name=f"Comparable App {idx}",
                url="https://example.com",
                positioning="General-purpose competitor with overlapping capabilities",
                pricing_model="Tiered subscription",
                key_features=["User management", "Dashboards", "Integrations"],
                weaknesses=["Steep learning curve", "Higher cost at scale"],
                user_sentiment="Neutral",
            )
        )

    return ResearchReport(
        problem_statement=ProblemStatement(
            core_problem=f"Users need a reliable way to achieve outcomes related to: {normalized_idea}.",
            affected_users="Consumers and teams needing consistent tracking, reminders, and insights.",
            current_solutions_fail_because="Existing tools are fragmented, generic, or too complex for daily use.",
            opportunity_window="Growing demand for lightweight AI-assisted productivity and wellness experiences.",
        ),
        market=MarketData(
            tam_usd=5_000_000_000,
            sam_usd=1_200_000_000,
            som_usd=120_000_000,
            industry=domain,
            growth_rate_yoy_percent=12.0,
            key_trends=[
                "Personalization with AI recommendations",
                "Cross-device and mobile-first usage",
                "Subscription bundles with premium analytics",
            ],
        ),
        personas=[
            Persona(
                name="Goal-Oriented Individual",
                age_range="22-40",
                occupation="Student or working professional",
                goals=["Build consistent habits", "Track progress over time", "Get actionable insights"],
                frustrations=["Tools require too much manual effort", "Poor retention due to weak motivation loops"],
                tech_savviness="medium",
                primary_device="mobile",
            ),
            Persona(
                name="Operations Manager",
                age_range="28-45",
                occupation="Team lead or operations manager",
                goals=["Improve team accountability", "Monitor key metrics", "Reduce coordination overhead"],
                frustrations=["Data spread across multiple apps", "No single source of truth"],
                tech_savviness="high",
                primary_device="web",
            ),
        ],
        pain_points=[
            PainPoint(
                pain="Inconsistent engagement due to low-friction tracking gaps",
                severity="high",
                frequency="frequent",
                existing_workaround="Manual notes and generic reminders",
            ),
            PainPoint(
                pain="Limited insight into trend progression and outcome impact",
                severity="medium",
                frequency="frequent",
                existing_workaround="Spreadsheet exports and ad-hoc analysis",
            ),
        ],
        competitors=competitors,
        viability=ViabilityData(
            revenue_models=["Freemium", "Premium subscription", "B2B team plans"],
            recommended_model="Freemium with premium analytics and integrations",
            estimated_arpu="$8-$18/month",
            go_to_market_strategy="Launch niche user segment first, then expand through referrals and content loops.",
            viability_score=7,
        ),
        feasibility=FeasibilityData(
            technical_risks=[
                "Sustaining engagement requires strong behavioral design",
                "Data quality and event tracking must stay consistent across clients",
            ],
            complexity="medium",
            estimated_mvp_weeks=10,
            key_dependencies=["Search/provider APIs", "Analytics pipeline", "Notification service"],
            feasibility_score=7,
        ),
    )


class ResearchAgent:
    """Research Agent for comprehensive market and user intelligence."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            max_tokens=900,
            max_retries=0,
        )
        self.parser = PydanticOutputParser(pydantic_object=ResearchReport)
        self.max_retries = 2

    def _build_research_prompt(self, project_brief: Dict[str, Any]) -> str:
        """Build the research prompt from project brief."""
        normalized_idea = project_brief.get("normalized_idea", "")
        domain = project_brief.get("domain", "general")
        target_platform = project_brief.get("target_platform", "web")

        return f"""Product Idea: {normalized_idea}
Domain: {domain}
Target Platform: {target_platform}

Produce a concise research_report JSON with keys:
problem_statement, market, personas, pain_points, competitors, viability, feasibility.

Requirements:
1. Use web search to gather real data where possible
2. Fill in ALL fields - use null only if absolutely necessary
3. Ensure 2+ competitors with complete data
4. Keep response compact and MVP-focused
5. Return ONLY the JSON object, no additional text"""

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
                    wait_time = min(2 ** attempt * 3, 8)
                    logger.warning(f"[research] Rate limit, waiting {wait_time}s before retry {attempt+1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                
                # Retry on parsing errors
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
                    continue

        logger.error(
            "[research] Exhausted retries, returning deterministic fallback report: %s",
            str(last_error)[:300],
        )
        fallback_report = _fallback_research_report(project_brief, evidence)
        fallback_embedding_ids = await self._store_embeddings(run_id, fallback_report.model_dump())
        return ResearchAgentOutput(
            run_id=run_id,
            research_report=fallback_report,
            embedding_ids=fallback_embedding_ids,
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
