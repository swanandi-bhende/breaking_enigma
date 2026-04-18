from typing import List, Dict, Any
import tiktoken


def chunk_text_by_tokens(
    text: str, chunk_size: int = 1000, overlap: int = 100
) -> List[str]:
    """Split text into overlapping chunks based on token count."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)

    chunks = []
    start = 0

    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append(chunk_text)
        start = end - overlap

    return chunks


def extract_json_from_response(response: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    import json
    import re

    cleaned = response.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise


def create_json_retry_prompt(error_context: str) -> str:
    """Create a prompt that asks LLM to fix JSON output."""
    return f"""
The previous response had the following issues:
{error_context}

Please fix the issues and return ONLY a valid JSON object.
Do NOT include any explanatory text, markdown code fences, or preamble.
"""


def format_research_for_embedding(research_report: Dict[str, Any]) -> List[str]:
    """Format research report sections for embedding."""
    sections = []

    if "problem_statement" in research_report:
        ps = research_report["problem_statement"]
        sections.append(f"Problem: {ps.get('core_problem', '')}")

    if "market" in research_report:
        m = research_report["market"]
        sections.append(
            f"Market: {m.get('industry', '')} - TAM: ${m.get('tam_usd', 0):,.0f}"
        )

    if "personas" in research_report:
        for p in research_report["personas"]:
            sections.append(f"Persona: {p.get('name', '')} - {p.get('occupation', '')}")

    if "pain_points" in research_report:
        for pp in research_report["pain_points"]:
            sections.append(
                f"Pain Point: {pp.get('pain', '')} (Severity: {pp.get('severity', '')})"
            )

    if "competitors" in research_report:
        for c in research_report["competitors"]:
            sections.append(
                f"Competitor: {c.get('name', '')} - {c.get('positioning', '')}"
            )

    return sections


def format_prd_for_embedding(prd: Dict[str, Any]) -> List[str]:
    """Format PRD sections for embedding."""
    sections = []

    if "product_vision" in prd:
        pv = prd["product_vision"]
        sections.append(f"Product: {pv.get('core_value_proposition', '')}")

    if "user_stories" in prd:
        for us in prd["user_stories"]:
            sections.append(
                f"User Story: {us.get('action', '')} so that {us.get('outcome', '')}"
            )

    if "features" in prd:
        features = prd["features"]
        for f in features.get("mvp", []):
            sections.append(
                f"MVP Feature: {f.get('name', '')} - {f.get('description', '')}"
            )

    return sections
