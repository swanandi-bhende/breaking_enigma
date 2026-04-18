from langchain_core.tools import tool
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from app.core.config import settings


@tool
def web_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Perform a web search to gather information about a topic.
    Use this for research, competitor analysis, and market research.

    Args:
        query: The search query
        num_results: Number of results to return (default 5)

    Returns:
        List of search results with title, url, and snippet
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return [{"error": f"Search failed with status {response.status_code}"}]

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for result in soup.select(".result")[:num_results]:
            title_elem = result.select_one(".result__title")
            link_elem = result.select_one(".result__url")
            snippet_elem = result.select_one(".result__snippet")

            if title_elem and link_elem:
                results.append(
                    {
                        "title": title_elem.get_text(strip=True),
                        "url": link_elem.get_text(strip=True),
                        "snippet": snippet_elem.get_text(strip=True)
                        if snippet_elem
                        else "",
                    }
                )

        return results if results else [{"error": "No results found"}]
    except Exception as e:
        return [{"error": str(e)}]


@tool
def serp_api_search(query: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Use SERP API for more structured search results.
    Use when you need more detailed results or when web_search fails.

    Args:
        query: The search query
        num_results: Number of results to return

    Returns:
        List of structured search results
    """
    if not settings.SERP_API_KEY:
        return [{"error": "SERP_API_KEY not configured"}]

    try:
        params = {
            "api_key": settings.SERP_API_KEY,
            "q": query,
            "num": num_results,
            "output": "json",
        }
        response = requests.get(
            "https://serpapi.com/search", params=params, timeout=15
        )

        if response.status_code != 200:
            return [{"error": f"SERP API failed with status {response.status_code}"}]

        data = response.json()
        results = []

        if "organic_results" in data:
            for result in data["organic_results"][:num_results]:
                results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", ""),
                        "position": result.get("position", 0),
                    }
                )

        return results
    except Exception as e:
        return [{"error": str(e)}]


@tool
def crunchbase_lookup(company_name: str) -> Dict[str, Any]:
    """
    Look up company information from Crunchbase.
    Use for competitor analysis and market research.

    Args:
        company_name: Name of the company to look up

    Returns:
        Company information including funding, description, and key people
    """
    if not settings.CRUNCHBASE_API_KEY:
        return {"error": "CRUNCHBASE_API_KEY not configured"}

    try:
        headers = {"X-Cb-User-Key": settings.CRUNCHBASE_API_KEY}
        response = requests.get(
            f"https://api.crunchbase.com/api/v4/organizations/{company_name}",
            headers=headers,
            timeout=10,
        )

        if response.status_code == 404:
            return {"error": f"Company '{company_name}' not found"}

        if response.status_code != 200:
            return {
                "error": f"Crunchbase lookup failed with status {response.status_code}"
            }

        data = response.json()

        return {
            "name": data.get("properties", {}).get("name", ""),
            "description": data.get("properties", {}).get("short_description", ""),
            "industry": data.get("properties", {}).get("industry", ""),
            "founded_year": data.get("properties", {}).get("founded_year", ""),
            "location": data.get("properties", {}).get("location", ""),
            "company_type": data.get("properties", {}).get("company_type", ""),
            "num_employees": data.get("properties", {}).get("num_employees_min", ""),
            "funding_total": data.get("properties", {}).get("funding_total", ""),
            "url": data.get("properties", {}).get("homepage_url", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def get_available_tools() -> List:
    """Return list of available tools for Research Agent."""
    tools = [web_search]
    if settings.SERP_API_KEY:
        tools.append(serp_api_search)
    if settings.CRUNCHBASE_API_KEY:
        tools.append(crunchbase_lookup)
    return tools
