"""
Designer Agent - Architectural and visual design engine.
Produces complete design_spec with screens, API spec, and data models.
Uses RAG to retrieve relevant research context from Qdrant.
"""

import logging
import re
import json
import asyncio
from typing import Dict, Any, List, Optional
import json_repair
from openai import AsyncOpenAI

from app.core.config import settings
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


logger = logging.getLogger(__name__)

_DOMAIN_STOPWORDS = {
  "a",
  "an",
  "and",
  "api",
  "app",
  "application",
  "as",
  "at",
  "be",
  "by",
  "can",
  "create",
  "data",
  "for",
  "from",
  "in",
  "is",
  "it",
  "of",
  "on",
  "or",
  "our",
  "product",
  "project",
  "so",
  "that",
  "the",
  "their",
  "them",
  "to",
  "user",
  "users",
  "with",
  "workflow",
}


def _extract_json_object(raw: str) -> Dict[str, Any]:
  text = raw.strip()
  try:
    parsed = json_repair.loads(text)
    if isinstance(parsed, dict):
      return parsed
    if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
      return parsed[0]
  except Exception:
    pass

  start = text.find("{")
  end = text.rfind("}")
  if start != -1 and end != -1 and end > start:
    try:
      parsed = json_repair.loads(text[start : end + 1])
      if isinstance(parsed, dict):
        return parsed
    except Exception:
      pass

  raise ValueError("Could not parse JSON object from designer response")


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
  message = str(exc).lower()
  markers = [
    "429",
    "too many requests",
    "quota",
    "rate limit",
    "exceeded your current quota",
    "tpm",
    "tpd",
  ]
  return any(marker in message for marker in markers)


def _is_daily_token_quota_error(exc: Exception) -> bool:
  message = str(exc).lower()
  return "tokens per day" in message or "tpd" in message


def _extract_retry_after_seconds(exc: Exception) -> float | None:
  message = str(exc).lower()
  # Handles strings like: "Please try again in 3m32.8896s" and "... in 7.8s"
  match_minutes = re.search(r"please try again in\s+([0-9]+)m([0-9.]+)s", message)
  if match_minutes:
    minutes = float(match_minutes.group(1))
    seconds = float(match_minutes.group(2))
    return minutes * 60.0 + seconds

  match_seconds = re.search(r"please try again in\s+([0-9.]+)s", message)
  if match_seconds:
    return float(match_seconds.group(1))

  return None


def _slugify(value: str) -> str:
  slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
  return slug or "product"


def _safe_text(value: Any, fallback: str = "-") -> str:
  if value is None:
    return fallback
  text = str(value).strip()
  return text if text else fallback


def _field(item: Any, key: str, default: Any = None) -> Any:
  if isinstance(item, dict):
    return item.get(key, default)
  return getattr(item, key, default)


def _pluralize(value: str) -> str:
  text = value.strip()
  if not text:
    return "items"
  lower = text.lower()
  if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
    return text[:-1] + "ies"
  if lower.endswith(("s", "x", "z", "ch", "sh")):
    return text + "es"
  return text + "s"


def _prd_text_blob(prd_dict: Dict[str, Any]) -> str:
  product_vision = prd_dict.get("product_vision", {}) if isinstance(prd_dict.get("product_vision", {}), dict) else {}
  user_stories = prd_dict.get("user_stories", []) if isinstance(prd_dict.get("user_stories", []), list) else []
  features = prd_dict.get("features", {}) if isinstance(prd_dict.get("features", {}), dict) else {}
  user_flow = prd_dict.get("user_flow", []) if isinstance(prd_dict.get("user_flow", []), list) else []

  parts: List[str] = [
    _safe_text(product_vision.get("elevator_pitch")),
    _safe_text(product_vision.get("target_user")),
    _safe_text(product_vision.get("core_value_proposition")),
    _safe_text(product_vision.get("success_definition")),
  ]

  for story in user_stories:
    if isinstance(story, dict):
      parts.extend([
        _safe_text(story.get("persona")),
        _safe_text(story.get("action")),
        _safe_text(story.get("outcome")),
      ])

  for bucket in (features.get("mvp", []), features.get("v1_1", []), features.get("v2_0", [])):
    for feature in bucket:
      if isinstance(feature, dict):
        parts.extend([
          _safe_text(feature.get("name")),
          _safe_text(feature.get("description")),
        ])

  for step in user_flow:
    if isinstance(step, dict):
      parts.extend([
        _safe_text(step.get("screen_name")),
        _safe_text(step.get("user_action")),
        _safe_text(step.get("system_response")),
      ])

  return " ".join(parts).lower()


def _extract_domain_keywords(prd_dict: Dict[str, Any], limit: int = 8) -> List[str]:
  tokens = re.findall(r"[a-z][a-z0-9]{2,}", _prd_text_blob(prd_dict))
  frequencies: Dict[str, int] = {}
  for token in tokens:
    if token in _DOMAIN_STOPWORDS:
      continue
    frequencies[token] = frequencies.get(token, 0) + 1

  ranked = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
  return [token for token, _ in ranked[:limit]]


def _derive_primary_label(prd_dict: Dict[str, Any], product_name: str) -> str:
  keywords = _extract_domain_keywords(prd_dict, limit=5)
  if keywords:
    return keywords[0].capitalize()

  product_tokens = re.findall(r"[A-Za-z0-9]+", product_name)
  for token in product_tokens:
    lower = token.lower()
    if lower not in _DOMAIN_STOPWORDS and len(lower) >= 3:
      return token.capitalize()
  return "Item"


def _infer_product_theme(prd_dict: Dict[str, Any]) -> Dict[str, Any]:
  product_vision = prd_dict.get("product_vision", {}) if isinstance(prd_dict.get("product_vision", {}), dict) else {}
  product_name = _safe_text(product_vision.get("elevator_pitch"), "Product Experience")
  target_user = _safe_text(product_vision.get("target_user"), "the user")
  text_blob = _prd_text_blob(prd_dict)

  if any(keyword in text_blob for keyword in ["expense", "receipt", "budget", "invoice", "spend", "spending"]):
    return {
      "theme_name": "expense",
      "primary_label": "Expense",
      "primary_label_plural": "Expenses",
      "component_prefix": "expense",
      "screen_focus": "expense tracking and reporting",
      "primary_actions": ["Add Expense", "Categorize Expense", "Upload Receipt", "View Report"],
      "secondary_actions": ["Filter by category", "Export CSV", "Set reminder"],
      "model_specs": [
        {
          "entity_name": "Expense",
          "table_name": "expenses",
          "fields": [
            {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
            {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
            {"name": "merchant", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
            {"name": "amount", "type": "decimal", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": None},
            {"name": "currency", "type": "text", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": "USD"},
            {"name": "category_id", "type": "uuid", "nullable": True, "unique": False, "indexed": True, "foreign_key": "categories.id", "default": None},
            {"name": "expense_date", "type": "datetime", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
            {"name": "payment_method", "type": "text", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
            {"name": "notes", "type": "text", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
            {"name": "receipt_url", "type": "text", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
          ],
          "relationships": [{"type": "one-to-many", "with_entity": "Category", "foreign_key": "category_id"}],
        },
        {
          "entity_name": "Category",
          "table_name": "categories",
          "fields": [
            {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
            {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
            {"name": "name", "type": "text", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
            {"name": "color", "type": "text", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
            {"name": "budget_limit", "type": "decimal", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
          ],
          "relationships": [],
        },
        {
          "entity_name": "Report",
          "table_name": "reports",
          "fields": [
            {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
            {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
            {"name": "period_start", "type": "datetime", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
            {"name": "period_end", "type": "datetime", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
            {"name": "total_amount", "type": "decimal", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": None},
            {"name": "export_url", "type": "text", "nullable": True, "unique": False, "indexed": False, "foreign_key": None, "default": None},
          ],
          "relationships": [],
        },
      ],
      "screen_prefix": "expense",
      "target_user": target_user,
      "product_name": product_name,
    }

  if any(keyword in text_blob for keyword in ["habit", "water", "wellness", "routine", "goal", "streak"]):
    return {
      "theme_name": "habit",
      "primary_label": "Habit",
      "primary_label_plural": "Habits",
      "component_prefix": "habit",
      "screen_focus": "habit tracking and streak management",
      "primary_actions": ["Create Habit", "Mark Complete", "View Streak", "Set Reminder"],
      "secondary_actions": ["See progress", "Adjust frequency", "Review missed days"],
      "model_specs": [
        {
          "entity_name": "Habit",
          "table_name": "habits",
          "fields": [
            {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
            {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
            {"name": "name", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
            {"name": "frequency", "type": "text", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": "daily"},
            {"name": "streak_count", "type": "integer", "nullable": False, "unique": False, "indexed": False, "foreign_key": None, "default": "0"},
          ],
          "relationships": [],
        },
      ],
      "screen_prefix": "habit",
      "target_user": target_user,
      "product_name": product_name,
    }

  primary_label = _derive_primary_label(prd_dict, product_name)
  primary_keyword = primary_label.lower()
  top_keywords = _extract_domain_keywords(prd_dict, limit=4)
  focus_tail = ", ".join(top_keywords[:3]) if top_keywords else "the primary user journey"
  return {
    "theme_name": "generic",
    "primary_label": primary_label,
    "primary_label_plural": _pluralize(primary_label),
    "component_prefix": _slugify(primary_keyword) or "product",
    "screen_focus": _safe_text(product_vision.get("core_value_proposition"), focus_tail),
    "primary_actions": [f"Create {primary_label}", f"Review {primary_label}", f"Continue {primary_label}"],
    "secondary_actions": ["Filter results", "Update details", "Resolve validation issues"],
    "model_specs": [
      {
        "entity_name": product_name.title(),
        "table_name": f"{_slugify(primary_keyword).replace('-', '_')}_items" if primary_keyword else "items",
        "fields": [
          {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
          {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
          {"name": "name", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
          {"name": "status", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "draft"},
        ],
        "relationships": [],
      },
    ],
    "screen_prefix": _slugify(primary_label),
    "target_user": target_user,
    "product_name": product_name,
  }


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
      "request_schema": {},
      "validation_rules": ["Validate required fields", "Return a structured validation error on failure"],
    },
    "responses": {
      "200": {
        "description": "Successful response",
        "response_schema": {},
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


def _screen_components_for_step(step_name: str, is_primary: bool, theme: Dict[str, Any]) -> List[Dict[str, Any]]:
  prefix = theme.get("component_prefix", "product")
  primary_action = theme.get("primary_actions", ["Continue"])[0]
  return [
    _build_component(f"{prefix}-top-nav", "navigation", {"style": "sticky", "product": theme.get("product_name")}, ["app.user"]),
    _build_component(f"{prefix}-summary", "display", {"variant": "summary", "title": step_name, "focus": theme.get("screen_focus")}, ["page.state"]),
    _build_component(
      f"{prefix}-primary-action",
      "form" if is_primary else "display",
      {"intent": "primary", "label": primary_action},
      ["page.state", "form.errors"],
    ),
    _build_component(f"{prefix}-status-feedback", "feedback", {"style": "inline", "product": theme.get("product_name")}, ["page.loading", "page.error"]),
  ]


def _to_plain_dict(value: Any) -> Dict[str, Any]:
  if isinstance(value, dict):
    return value
  if hasattr(value, "model_dump"):
    dumped = value.model_dump()
    return dumped if isinstance(dumped, dict) else {}
  if hasattr(value, "dict"):
    dumped = value.dict()
    return dumped if isinstance(dumped, dict) else {}
  return {}


def _build_design_spec_from_prd(prd: PRD) -> Dict[str, Any]:
  prd_dict = _to_plain_dict(prd)
  product_vision = prd_dict.get("product_vision", {}) if isinstance(prd_dict.get("product_vision", {}), dict) else {}
  user_stories = list(prd_dict.get("user_stories", []))
  user_flow = list(prd_dict.get("user_flow", []))
  features = prd_dict.get("features", {}) if isinstance(prd_dict.get("features", {}), dict) else {}

  project_name = _safe_text(product_vision.get("elevator_pitch"), "Product Experience")
  theme = _infer_product_theme(prd_dict)
  domain_keywords = _extract_domain_keywords(prd_dict, limit=4)

  mvp_features = list(features.get("mvp", []))
  v11_features = list(features.get("v1_1", []))
  v20_features = list(features.get("v2_0", []))

  target_user = _safe_text(product_vision.get("target_user"), theme.get("target_user", "the user"))
  core_value = _safe_text(product_vision.get("core_value_proposition"), project_name)
  primary_resource_singular = _safe_text(theme.get("primary_label"), "item").lower()
  primary_resource_plural = _safe_text(theme.get("primary_label_plural"), _pluralize(primary_resource_singular)).lower()
  primary_resource_path = _slugify(primary_resource_plural)
  secondary_resource_path = _slugify(domain_keywords[1]) if len(domain_keywords) > 1 else "insights"

  screens: List[Dict[str, Any]] = []
  if user_flow:
    for index, flow_step in enumerate(user_flow[:5]):
      step_name = _safe_text(_field(flow_step, "screen_name"), f"Step {index + 1}")
      step_slug = _slugify(step_name)
      step_action = _safe_text(_field(flow_step, "user_action"), "Continue")
      system_response = _safe_text(_field(flow_step, "system_response"), "Show the next relevant state")
      screens.append(
        _build_screen(
          screen_id=f"screen-{step_slug}",
          screen_name=step_name,
          route="/" if index == 0 else f"/{step_slug}",
          purpose=f"Support step {_field(flow_step, 'step', index + 1)}: {step_action} for {target_user}. {system_response}.",
          components=_screen_components_for_step(step_name, index == 0, theme),
          ux_decisions=[
            f"Keep the primary action visible above the fold for {project_name}",
            f"Use progressive disclosure for {theme.get('screen_focus', 'the workflow')}",
            f"Show inline validation and status feedback for {target_user}",
          ],
          edge_cases=[
            f"Loading state while {theme.get('primary_label_plural', 'items').lower()} are fetched",
            f"Validation errors while saving {theme.get('primary_label', 'data').lower()} entries",
            f"Empty state when there is no saved {theme.get('primary_label_plural', 'data').lower()}",
          ],
          wireframe_description=(
            f"Header with navigation, a focused content card for {step_name} in the {project_name} experience, "
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
        purpose=f"Introduce {project_name} and guide {target_user} into the primary workflow.",
        components=_screen_components_for_step(project_name, True, theme),
        ux_decisions=[
          f"Keep onboarding lightweight for {project_name}",
          f"Highlight the single primary call to action for {target_user}",
          f"Use a clean mobile-first layout that supports {core_value}",
        ],
        edge_cases=[
          f"No {theme.get('primary_label_plural', 'data').lower()} available",
          "API load failure",
          "User has not completed onboarding",
        ],
        wireframe_description=f"Top navigation, hero summary block, action cards centered on {theme.get('screen_focus', 'the product workflow')}, and a compact feedback banner.",
      )
    )

  if mvp_features:
    primary_feature = mvp_features[0]
    primary_feature_name = _safe_text(_field(primary_feature, "name"), "Primary Feature")
    primary_feature_desc = _safe_text(_field(primary_feature, "description"), f"Core capability for {project_name}")
    screens.append(
      _build_screen(
        screen_id=f"screen-{_slugify(primary_feature_name)}",
        screen_name=primary_feature_name,
        route=f"/{_slugify(primary_feature_name)}",
        purpose=f"{primary_feature_desc} for {project_name}.",
        components=[
          _build_component(f"{theme.get('component_prefix', 'product')}-section-header", "layout", {"title": primary_feature_name}, ["feature.state"]),
          _build_component(f"{theme.get('component_prefix', 'product')}-card-grid", "display", {"cards": "primary", "feature": primary_feature_name}, ["feature.items"]),
          _build_component(f"{theme.get('component_prefix', 'product')}-primary-cta", "form", {"label": theme.get("primary_actions", ["Continue"])[0]}, ["feature.form"]),
        ],
        ux_decisions=[
          f"Prioritize {primary_feature_name.lower()} completion over decorative elements",
          f"Keep actions one click away for {target_user}",
        ],
        edge_cases=[
          f"No {theme.get('primary_label_plural', 'items').lower()} returned",
          "User input is incomplete",
        ],
        wireframe_description=f"Section header followed by a structured feature card grid for {primary_feature_name} in {project_name}.",
      )
    )

  interaction_steps = [
    f"Step {_field(step, 'step', idx + 1)}: {_safe_text(_field(step, 'screen_name'), f'Step {idx + 1}')} - {_safe_text(_field(step, 'user_action'), 'Continue')}"
    for idx, step in enumerate(user_flow[:5])
  ] or [
    "Open the home screen",
    "Review the primary action area",
    "Submit or continue the workflow",
    "Confirm success and surface the next best action",
  ]

  user_story_ids = [
    _safe_text(_field(story, "id"))
    for story in user_stories
    if _field(story, "id")
  ]
  if not user_story_ids:
    user_story_ids = ["US-001"]

  api_spec = [
    _build_endpoint(
      endpoint_id=f"api-{primary_resource_path}-list",
      method="GET",
      path=f"/api/v1/{primary_resource_path}",
      description=f"List all {primary_resource_plural} for {target_user} in {project_name}, including state needed for {core_value}.",
      maps_to_user_stories=user_story_ids[:2],
      auth_required=True,
    ),
    _build_endpoint(
      endpoint_id=f"api-{primary_resource_path}-create",
      method="POST",
      path=f"/api/v1/{primary_resource_path}",
      description=f"Create a new {primary_resource_singular} from the core flow ({theme.get('screen_focus', 'workflow')}) for {target_user}.",
      maps_to_user_stories=user_story_ids[:3],
      auth_required=True,
    ),
    _build_endpoint(
      endpoint_id=f"api-{primary_resource_path}-detail",
      method="GET",
      path=f"/api/v1/{primary_resource_path}/{{resource_id}}",
      description=f"Return detailed {primary_resource_singular} data, related context, and workflow state for {project_name}.",
      maps_to_user_stories=user_story_ids[:3],
      auth_required=True,
    ),
  ]

  if domain_keywords:
    api_spec.append(
      _build_endpoint(
        endpoint_id=f"api-{primary_resource_path}-{secondary_resource_path}",
        method="GET",
        path=f"/api/v1/{primary_resource_path}/{{resource_id}}/{secondary_resource_path}",
        description=f"Fetch {secondary_resource_path.replace('-', ' ')} context tied to the selected {primary_resource_singular}.",
        maps_to_user_stories=user_story_ids[:2],
        auth_required=True,
      )
    )

  if v11_features:
    api_spec.append(
      _build_endpoint(
        endpoint_id=f"api-{primary_resource_path}-update",
        method="PATCH",
        path=f"/api/v1/{primary_resource_path}/{{resource_id}}",
        description=f"Update a saved {primary_resource_singular} draft or configuration for {project_name}.",
        maps_to_user_stories=user_story_ids[1:4] or user_story_ids[:1],
        auth_required=True,
      )
    )

  if v20_features:
    api_spec.append(
      _build_endpoint(
        endpoint_id=f"api-{primary_resource_path}-archive",
        method="DELETE",
        path=f"/api/v1/{primary_resource_path}/{{resource_id}}",
        description=f"Archive or remove a completed {primary_resource_singular} in {project_name}.",
        maps_to_user_stories=user_story_ids[-2:] or user_story_ids[:1],
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
      [],
    ),
  ]

  for model_spec in theme.get("model_specs", []):
    if isinstance(model_spec, dict):
      data_models.append(
        _build_data_model(
          _safe_text(model_spec.get("entity_name"), "Item"),
          _safe_text(model_spec.get("table_name"), "items"),
          list(model_spec.get("fields", [])),
          list(model_spec.get("relationships", [])),
        )
      )

  if theme.get("theme_name") == "generic" and mvp_features:
    primary_feature_name = _safe_text(_field(mvp_features[0], "name"), "PrimaryItem")
    data_models.append(
      _build_data_model(
        primary_feature_name,
        f"{_slugify(primary_feature_name).replace('-', '_')}_records",
        [
          {"name": "id", "type": "uuid", "nullable": False, "unique": True, "indexed": True, "foreign_key": None, "default": None},
          {"name": "user_id", "type": "uuid", "nullable": False, "unique": False, "indexed": True, "foreign_key": "users.id", "default": None},
          {"name": "title", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": None},
          {"name": "status", "type": "text", "nullable": False, "unique": False, "indexed": True, "foreign_key": None, "default": "draft"},
        ],
        [],
      )
    )

  design_spec = DesignSpec(
    screens=screens,
    interaction_flows=[
      InteractionFlow(
        flow_id="flow-primary",
        flow_name=f"Primary {primary_resource_singular} workflow for {project_name}",
        trigger="User opens the product and starts the main task",
        steps=interaction_steps,
        happy_path_end=f"{target_user} completes the core task and sees a confirmation state",
        failure_paths=[
          f"Validation error while saving {theme.get('primary_label', 'data').lower()}",
          "Network timeout",
          f"Empty results state for {theme.get('primary_label_plural', 'items').lower()}",
        ],
      ),
      InteractionFlow(
        flow_id="flow-recovery",
        flow_name=f"{primary_resource_singular.capitalize()} error and recovery flow",
        trigger=f"An action fails or returns incomplete {theme.get('primary_label', 'data').lower()}",
        steps=[
          "Show inline error feedback",
          "Preserve user input",
          "Offer retry and back navigation",
        ],
        happy_path_end=f"{target_user} retries successfully and resumes the main workflow",
        failure_paths=["Repeated API failure", "Invalid input format"],
      ),
    ],
    system_architecture=SystemArchitecture(
      frontend=f"Next.js client with reusable {primary_resource_singular}-oriented screen components for {project_name}",
      backend=f"FastAPI service orchestrating agent workflows and {primary_resource_plural} APIs for {target_user}",
      database=f"PostgreSQL for durable {primary_resource_plural} data and workflow state",
      cache="Redis for events, queues, and short-lived state",
      external_services=[
        "Qdrant for retrieval context",
        "LLM provider configured in environment",
        f"Domain analytics for {primary_resource_plural}",
      ],
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

    def __init__(self, provider: Optional[str] = None):
      selected_provider = (provider or "groq").lower()

      if selected_provider == "gemini":
        api_key = settings.GEMINI_API_KEY
        model = settings.GEMINI_MODEL
        base_url = settings.GEMINI_BASE_URL
      else:
        selected_provider = "groq"
        api_key = settings.OPENAI_API_KEY
        model = settings.OPENAI_MODEL
        base_url = settings.OPENAI_BASE_URL

      if not api_key:
        raise ValueError(f"Missing API key for provider={selected_provider}")

      self.provider = selected_provider
      self.model_name = model

      self.client = AsyncOpenAI(
          api_key=api_key,
          base_url=base_url,
          max_retries=0,
      )
      self.max_retries = 5
      self.fallback_enabled = bool(settings.GEMINI_API_KEY)

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

            # Lazy import keeps Designer usable even if optional langchain stack is unavailable.
            from app.core.llm import llm_client

            query_vector = await llm_client.embed_query(query)
            results = await qdrant_manager.retrieve_research_context(
                query=query,
                query_vector=query_vector,
                run_id=run_id,
                limit=5,
            )
            return [r["text"] for r in results]
        except Exception as e:
            print(f"Warning: Failed to retrieve research context: {e}")
            return []

    def _build_design_prompt(self, prd: PRD, research_context: List[str]) -> str:
        """Build the design prompt from PRD and research context."""
        prd_dict = _to_plain_dict(prd)

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
Return only a valid JSON object matching the specified design_spec schema."""

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

        logger.info(
          "[designer] generating design_spec via provider=%s model=%s run_id=%s",
          self.provider,
          self.model_name,
          run_id,
        )

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": DESIGNER_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"},
                )

                raw_content = (response.choices[0].message.content or "").strip()
                parsed = _extract_json_object(raw_content)
                spec_payload = parsed.get("design_spec") if isinstance(parsed.get("design_spec"), dict) else parsed
                result = DesignSpec.model_validate(spec_payload)

                logger.info(
                    "[designer] generated design_spec via llm with screens=%s flows=%s apis=%s",
                    len(result.screens),
                    len(result.interaction_flows),
                    len(result.api_spec),
                )

                return DesignerAgentOutput(run_id=run_id, design_spec=result)

            except Exception as e:
                last_error = e
                logger.warning("[designer] attempt %s failed: %s", attempt + 1, str(e)[:250])
                if self.provider == "gemini" and _is_quota_or_rate_limit_error(e):
                    # Gemini quota exhaustion should immediately fall back to deterministic spec.
                    raise RuntimeError(f"GEMINI_QUOTA_EXCEEDED: {e}") from e
                if self.provider == "groq" and self.fallback_enabled and _is_daily_token_quota_error(e):
                    # Daily quota exhaustion won't recover quickly; hand over to Gemini at wrapper level.
                    raise RuntimeError(f"GROQ_DAILY_QUOTA_EXCEEDED: {e}") from e
                if attempt < self.max_retries - 1:
                    if _is_quota_or_rate_limit_error(e):
                        retry_after = _extract_retry_after_seconds(e)
                        wait_seconds = 30.0 if retry_after is None else min(retry_after + 1.0, 45.0)
                        logger.warning("[designer] quota/rate-limit detected; sleeping for %.1fs", wait_seconds)
                        await asyncio.sleep(wait_seconds)
                    else:
                        await asyncio.sleep(5.0)
                    continue

        raise Exception(
            f"Designer Agent failed after {self.max_retries} attempts: {last_error}"
        )


async def run_designer_agent(input_data: DesignerAgentInput | Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point for Designer Agent.

    Uses the LLM to generate a design spec specific to the user prompt.
    """
    if isinstance(input_data, dict):
        input_data = DesignerAgentInput.model_validate(input_data)

    run_id = str(input_data.run_id)
    
    agent = DesignerAgent(provider="groq")
    output: DesignerAgentOutput | None = None

    try:
      output = await agent.run(input_data)
    except Exception as groq_error:
      if settings.GEMINI_API_KEY and _is_quota_or_rate_limit_error(groq_error):
        logger.warning(
          "[designer] Groq failed due to quota/rate-limit; retrying with Gemini. run_id=%s error=%s",
          run_id,
          str(groq_error)[:250],
        )
        try:
          agent = DesignerAgent(provider="gemini")
          output = await agent.run(input_data)
        except Exception as gemini_error:
          logger.warning(
            "[designer] Gemini fallback failed; using deterministic PRD-based spec. run_id=%s error=%s",
            run_id,
            str(gemini_error)[:250],
          )
      else:
        logger.warning(
          "[designer] Non-retriable LLM error; using deterministic PRD-based spec. run_id=%s error=%s",
          run_id,
          str(groq_error)[:250],
        )

    if output is None:
      deterministic_spec = _build_design_spec_from_prd(prd=input_data.prd)
      logger.info("[designer] generated deterministic design_spec run_id=%s", run_id)
      return {
        "run_id": run_id,
        "design_spec": deterministic_spec,
      }

    design_spec = output.design_spec.model_dump(mode="json") if hasattr(output.design_spec, 'model_dump') else output.design_spec
    logger.info(
      "[designer] Successfully generated LLM design_spec run_id=%s provider=%s model=%s screens=%s flows=%s apis=%s",
      run_id,
      agent.provider,
      agent.model_name,
      len(design_spec.get("screens", [])),
      len(design_spec.get("interaction_flows", [])),
      len(design_spec.get("api_spec", [])),
    )

    return {
      "run_id": run_id,
      "design_spec": design_spec,
    }
