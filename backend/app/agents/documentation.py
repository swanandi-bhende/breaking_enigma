from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Tuple

from app.schemas.agents import DocumentationAgentInput

logger = logging.getLogger(__name__)

DOCUMENT_FILENAMES = [
    "README.md",
    "API_REFERENCE.md",
    "ARCHITECTURE.md",
    "KNOWN_ISSUES.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
]


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        return {key: val for key, val in vars(value).items() if not key.startswith("_")}
    return {}


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _enum_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    raw = getattr(value, "value", value)
    return _text(raw, default)


def _items(value: Any, key: str) -> List[Any]:
    items = _get(value, key, [])
    return list(items) if isinstance(items, list) else []


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _render_bullets(items: Iterable[str], empty_message: str) -> str:
    lines = [f"- {item}" for item in items if _text(item)]
    if not lines:
        return empty_message
    return "\n".join(lines)


def _render_table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return ""

    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_rows = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_row, separator_row, *body_rows])


def _normalize_feature_item(item: Any) -> str:
    feature = _text(_get(item, "feature", _get(item, "name", "")))
    reason = _text(_get(item, "reason", _get(item, "description", "")))
    if feature and reason:
        return f"{feature} — {reason}"
    return feature or reason


def _implemented_features(developer_output: Any) -> List[str]:
    return [
        _text(item)
        for item in _items(developer_output, "features_implemented")
        if _text(item)
    ]


def _planned_features(developer_output: Any) -> List[str]:
    return [
        _normalize_feature_item(item)
        for item in _items(developer_output, "features_skipped")
        if _normalize_feature_item(item)
    ]


def _open_issues(qa_output: Any) -> List[Any]:
    issues: List[Any] = []
    for bug in _items(qa_output, "bugs"):
        status = _enum_text(_get(bug, "status"), "OPEN").upper()
        if status in {"OPEN", "IN_PROGRESS"}:
            issues.append(bug)
    return issues


def _build_known_issues_markdown(qa_output: Any) -> str:
    bugs = _open_issues(qa_output)
    if not bugs:
        return "# Known Issues\n\nNo open or in-progress QA bugs were reported for this run."

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_bugs = sorted(
        bugs,
        key=lambda bug: (
            severity_rank.get(_enum_text(_get(bug, "severity"), "LOW").upper(), 9),
            _text(_get(bug, "bug_id")),
        ),
    )

    lines = ["# Known Issues", "", "Only open or in-progress bugs are listed below.", ""]
    for bug in sorted_bugs:
        severity = _enum_text(_get(bug, "severity"), "low").upper()
        title = _text(_get(bug, "title"), "Issue")
        description = _text(_get(bug, "description"), "No description provided.")
        workaround = _text(_get(bug, "suggested_fix"), "No workaround provided.")
        status = _enum_text(_get(bug, "status"), "OPEN").upper()
        lines.extend(
            [
                f"## {_text(_get(bug, 'bug_id'), 'BUG')} — {title}",
                f"- Severity: {severity}",
                f"- Description: {description}",
                f"- Workaround: {workaround}",
                f"- Fix status: {status}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def _build_readme_markdown(input_data: DocumentationAgentInput) -> str:
    prd = input_data.prd
    design_spec = input_data.design_spec
    developer_output = input_data.developer_output
    devops_output = input_data.devops_output

    product_vision = prd.product_vision
    built_features = _implemented_features(developer_output)
    planned_features = _planned_features(developer_output)
    tech_stack = _as_dict(design_spec.system_architecture)

    quick_start_commands = [command for command in _items(devops_output, "startup_commands") if _text(command)]
    env_vars = _items(devops_output, "environment_variables")
    deployment_url = _text(_get(devops_output, "deployment_url"), "")

    lines = [
        f"# {product_vision.elevator_pitch}",
        "",
        "## Product Overview",
        f"{_text(product_vision.core_value_proposition)}",
        "",
        f"- Target user: {_text(product_vision.target_user)}",
        f"- Success definition: {_text(product_vision.success_definition)}",
        f"- Source: pm.output.product_vision",
        "",
        "## Quick Start",
    ]

    if quick_start_commands:
        lines.extend([
            "Commands from deployment.output:",
            "",
        ])
        for command in quick_start_commands:
            lines.append("```bash")
            lines.append(command)
            lines.append("```")
    else:
        lines.extend([
            "Commands from deployment.output were not provided in the structured outputs for this run.",
        ])

    if deployment_url:
        lines.extend(["", f"- Deployment URL: {deployment_url}"])

    lines.extend([
        "",
        "## Features",
        "### BUILT_FEATURES",
        _render_bullets(built_features, "- No features were explicitly marked IMPLEMENTED in developer.output."),
        "",
        "### Coming Soon",
        _render_bullets(planned_features, "- No features were explicitly marked NOT_IMPLEMENTED in developer.output."),
        "",
        "## Tech Stack",
    ])

    tech_rows = [
        ["Frontend", _text(tech_stack.get("frontend"), "")],
        ["Backend", _text(tech_stack.get("backend"), "")],
        ["Database", _text(tech_stack.get("database"), "")],
        ["Cache", _text(tech_stack.get("cache"), "None")],
        ["External services", ", ".join(_text(item) for item in _get(tech_stack, "external_services", []) if _text(item)) or "None"],
        ["Communication patterns", "; ".join(f"{_text(key)}: {_text(value)}" for key, value in _as_dict(_get(tech_stack, "communication_patterns", {})).items()) or "None"],
    ]
    lines.append(_render_table(["Layer", "Value"], tech_rows))

    lines.extend([
        "",
        "## Environment Variables",
    ])

    env_rows = []
    for env_var in env_vars:
        env_rows.append([
            _text(_get(env_var, "key"), ""),
            _text(_get(env_var, "description"), ""),
            "Yes" if bool(_get(env_var, "required", True)) else "No",
            _text(_get(env_var, "example_value"), ""),
        ])
    lines.append(_render_table(["Key", "Description", "Required", "Example"], env_rows) or "No environment variables were provided in deployment.output.")

    api_spec = _items(design_spec, "api_spec")
    if api_spec:
        lines.extend([
            "",
            "## Basic Usage",
            "The following API entry points are available in the design spec:",
            "",
        ])
        for endpoint in api_spec:
            method = _text(_get(endpoint, "method"), "GET")
            path = _text(_get(endpoint, "path"), "")
            description = _text(_get(endpoint, "description"), "")
            lines.append(f"- `{method} {path}` — {description}")
    else:
        lines.extend([
            "",
            "## Basic Usage",
            "No API contracts were provided in the design spec.",
        ])

    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def _flatten_schema_properties(schema: Dict[str, Any], prefix: str = "") -> List[Tuple[str, str, str]]:
    schema_type = _text(schema.get("type"), "object")
    rows: List[Tuple[str, str, str]] = []

    if schema_type == "object":
        properties = schema.get("properties", {})
        required_fields = schema.get("required", []) if isinstance(schema.get("required", []), list) else []
        for name, child in properties.items() if isinstance(properties, dict) else []:
            child_dict = _as_dict(child)
            field_name = f"{prefix}.{name}" if prefix else name
            child_type = _schema_type_label(child_dict)
            rules = _schema_rules(child_dict, field_name=name, required_fields=required_fields)
            if _text(child_dict.get("type"), "object") == "object" and child_dict.get("properties"):
                rows.append((field_name, child_type, rules))
                rows.extend(_flatten_schema_properties(child_dict, field_name))
            else:
                rows.append((field_name, child_type, rules))
        return rows

    if schema_type == "array":
        items = _as_dict(schema.get("items", {}))
        rows.append((prefix or "items", f"array<{_schema_type_label(items)}>", _schema_rules(schema)))
        if items.get("properties"):
            rows.extend(_flatten_schema_properties(items, f"{prefix}[]" if prefix else "items[]"))
        return rows

    rows.append((prefix or "value", schema_type, _schema_rules(schema)))
    return rows


def _schema_type_label(schema: Dict[str, Any]) -> str:
    schema_type = _text(schema.get("type"), "object")
    if schema_type == "array":
        items = _as_dict(schema.get("items", {}))
        return f"array<{_schema_type_label(items)}>"
    if schema_type == "object":
        return "object"
    if schema_type == "integer":
        return "integer"
    if schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    return schema_type


def _schema_rules(schema: Dict[str, Any], field_name: str | None = None, required_fields: List[str] | None = None) -> str:
    rules: List[str] = []
    required_fields = required_fields or []
    if field_name and field_name in required_fields:
        rules.append("required")
    if schema.get("nullable"):
        rules.append("nullable")
    if schema.get("minLength") is not None:
        rules.append(f"minLength={schema['minLength']}")
    if schema.get("maxLength") is not None:
        rules.append(f"maxLength={schema['maxLength']}")
    if schema.get("minimum") is not None:
        rules.append(f"minimum={schema['minimum']}")
    if schema.get("maximum") is not None:
        rules.append(f"maximum={schema['maximum']}")
    if schema.get("pattern"):
        rules.append(f"pattern={schema['pattern']}")
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        rules.append("enum: " + ", ".join(_text(item) for item in schema["enum"]))
    if schema.get("format"):
        rules.append(f"format={schema['format']}")
    return "; ".join(rules)


def _select_success_response(responses: Dict[str, Any]) -> Tuple[str, Dict[str, Any]] | Tuple[None, None]:
    for code in ("200", "201", "202", "204"):
        response = responses.get(code)
        if response is not None:
            return code, _as_dict(response)
    for code, response in responses.items():
        if str(code).startswith("2"):
            return str(code), _as_dict(response)
    return None, None


def _build_api_reference_markdown(design_spec: Any) -> str:
    endpoints = _items(design_spec, "api_spec")
    if not endpoints:
        return "# API Reference\n\nNo API contracts were provided in the design spec.\n"

    lines = ["# API Reference", "", "This document is generated directly from design_spec.api_spec.", ""]
    for endpoint in endpoints:
        endpoint_id = _text(_get(endpoint, "endpoint_id"), "endpoint")
        method = _text(_get(endpoint, "method"), "GET")
        path = _text(_get(endpoint, "path"), "")
        auth_required = "required" if bool(_get(endpoint, "auth_required", False)) else "not required"
        description = _text(_get(endpoint, "description"), "")
        request_body = _as_dict(_get(endpoint, "request_body", {}))
        request_schema = _as_dict(request_body.get("request_schema", {}))
        validation_rules = [
            _text(rule)
            for rule in _items(request_body, "validation_rules")
            if _text(rule)
        ]
        responses = _as_dict(_get(endpoint, "responses", {}))
        success_code, success_response = _select_success_response(responses)

        lines.extend([
            f"## {method} {path}",
            f"- Endpoint ID: `{endpoint_id}`",
            f"- Authentication: {auth_required}",
            f"- Description: {description}",
            "",
            "### Request Body",
        ])

        field_rows = _flatten_schema_properties(request_schema)
        if field_rows:
            lines.append(_render_table(["Field", "Type", "Validation"], [[name, type_name, rules or "-"] for name, type_name, rules in field_rows]))
        else:
            lines.append("No request body fields are defined in the design spec.")
        if validation_rules:
            lines.extend([
                "",
                "Validation rules:",
                _render_bullets(validation_rules, "- No validation rules were defined."),
            ])
        else:
            lines.extend([
                "",
                "Validation rules:",
                "- No validation rules were defined.",
            ])

        lines.extend([
            "",
            "### Success Response",
        ])
        if success_code is not None and success_response is not None:
            lines.extend([
                f"- Status: {success_code}",
                f"- Description: {_text(success_response.get('description'), 'Successful response')}",
                "- Example:",
                "```json",
                _json_block(success_response.get("example", {})),
                "```",
            ])
        else:
            lines.append("No explicit success response example was provided in the design spec.")

        error_rows = []
        for code, response in responses.items():
            if str(code).startswith("2"):
                continue
            response_dict = _as_dict(response)
            error_rows.append([str(code), _text(response_dict.get("description"), "")])

        lines.extend([
            "",
            "### Error Codes",
        ])
        if error_rows:
            lines.append(_render_table(["Code", "Meaning"], error_rows))
        else:
            lines.append("No explicit non-2xx error responses were defined in the design spec.")

        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_architecture_markdown(input_data: DocumentationAgentInput) -> str:
    architecture = _as_dict(input_data.design_spec.system_architecture)
    implementation_plan = _as_dict(getattr(input_data.developer_output, "implementation_plan", {}))
    product_name = _text(input_data.prd.product_vision.elevator_pitch, "Generated Product")

    lines = [
        "# Architecture",
        "",
        f"{product_name} is built as a multi-agent workflow with a Next.js frontend, FastAPI backend, and shared persistence/memory services.",
        "",
        "## System Overview",
        f"{_text(architecture.get('frontend'), 'Frontend')} | {_text(architecture.get('backend'), 'Backend')} | {_text(architecture.get('database'), 'Database')}",
        "",
        "## Key Components",
        f"- Frontend: {_text(architecture.get('frontend'), 'Not specified')}",
        f"- Backend: {_text(architecture.get('backend'), 'Not specified')}",
        f"- Database: {_text(architecture.get('database'), 'Not specified')}",
        f"- Cache: {_text(architecture.get('cache'), 'None')}",
        f"- External services: {', '.join(_text(item) for item in _get(architecture, 'external_services', []) if _text(item)) or 'None'}",
        "",
        "## Data Flow",
    ]

    flows = _items(input_data.design_spec, "interaction_flows")
    if flows:
        for flow in flows:
            lines.extend([
                f"- {_text(_get(flow, 'flow_name'), 'Flow')}: {_text(_get(flow, 'trigger'), 'trigger')} → {_text(_get(flow, 'happy_path_end'), 'completion')}",
            ])
    else:
        lines.append("- The workflow proceeds from idea intake to agent orchestration, then into QA-gated finalization.")

    lines.extend([
        "",
        "## Design Decisions",
    ])

    decisions = [
        _text(item)
        for item in _items(implementation_plan, "key_architectural_decisions")
        if _text(item)
    ]
    lines.append(_render_bullets(decisions, "- No explicit architectural decisions were recorded in developer.output."))

    tradeoffs = [
        _text(item)
        for item in _items(implementation_plan, "risk_mitigation_plan")
        if _text(item)
    ]
    lines.extend([
        "",
        "## Trade-offs",
        _render_bullets(tradeoffs, "- No trade-offs were recorded in developer.output."),
    ])

    return "\n".join(lines).strip() + "\n"


def _build_contributing_markdown(input_data: DocumentationAgentInput) -> str:
    devops_output = input_data.devops_output
    startup_commands = [command for command in _items(devops_output, "startup_commands") if _text(command)]
    env_vars = _items(devops_output, "environment_variables")

    lines = [
        "# Contributing",
        "",
        "## Local Setup",
    ]
    if startup_commands:
        lines.append("Use the exact startup commands captured in deployment.output:")
        for command in startup_commands:
            lines.append(f"- `{_text(command)}`")
    else:
        lines.append("No deployment startup commands were provided in the structured outputs.")

    lines.extend([
        "",
        "## How to Run Project",
        "- Start the stack using the deployment commands above.",
        "- Run backend tests with `pytest tests -q` from the backend workspace when the Python environment is configured.",
        "",
        "## Code Structure",
        "- `backend/app/agents`: agent implementations and fallback logic.",
        "- `backend/app/api`: HTTP and WebSocket endpoints.",
        "- `backend/app/workflow`: orchestration, routing, and shared state helpers.",
        "- `frontend/src`: UI, canvas panels, store, and hooks.",
        "- `backend/tests`: backend regression coverage.",
        "",
        "## Adding Features",
        "- Keep changes aligned with the agent input/output schemas.",
        "- Update the corresponding docs outputs when APIs or environment variables change.",
        "- Add or adjust tests for any new workflow or contract behavior.",
        "",
        "## PR Guidelines",
        "- Keep pull requests focused on one concern.",
        "- Include tests for contract or workflow changes.",
        "- Avoid mixing documentation-only and behavior changes unless they are tightly coupled.",
    ])

    if env_vars:
        lines.extend([
            "",
            "## Environment Variables",
        ])
        for env_var in env_vars:
            lines.append(
                f"- `{_text(_get(env_var, 'key'))}` ({'required' if bool(_get(env_var, 'required', True)) else 'optional'})"
            )

    return "\n".join(lines).strip() + "\n"


def _build_changelog_markdown(input_data: DocumentationAgentInput) -> str:
    version = "1.0.0"
    implemented = _implemented_features(input_data.developer_output)
    resolved_bugs = [bug for bug in _items(input_data.qa_output, "bugs") if _enum_text(_get(bug, "status"), "").upper() == "RESOLVED"]
    improvements = [
        _text(item)
        for item in _items(input_data.developer_output, "tech_debt_logged")
        if _text(item)
    ]

    lines = [
        "# Changelog",
        "",
        f"## Version {version}",
        "",
        "### Features Added",
        _render_bullets(implemented, "- No features were explicitly marked IMPLEMENTED in developer.output."),
        "",
        "### Bug Fixes",
    ]
    if resolved_bugs:
        for bug in resolved_bugs:
            lines.append(f"- {_text(_get(bug, 'bug_id'), 'BUG')} — {_text(_get(bug, 'title'), 'Bug fix')}")
    else:
        lines.append("- No bugs were explicitly marked RESOLVED in the source outputs.")

    lines.extend([
        "",
        "### Improvements",
        _render_bullets(improvements, "- No developer tech-debt or improvement notes were recorded."),
    ])

    return "\n".join(lines).strip() + "\n"


class DocumentationAgent:
    def __init__(self):
        self.name = "Documentation Agent"

    async def execute(self, run_id: str, all_artifacts: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[documentation] executing class wrapper run_id=%s", run_id)
        payload = {
            "run_id": run_id,
            "research_report": all_artifacts.get("research_report"),
            "prd": all_artifacts.get("prd"),
            "design_spec": all_artifacts.get("design_spec"),
            "developer_output": all_artifacts.get("developer_output"),
            "qa_output": all_artifacts.get("qa_output"),
            "devops_output": all_artifacts.get("devops_output"),
        }
        return await run_documentation_agent(payload)


async def run_documentation_agent(input_data: DocumentationAgentInput | Dict[str, Any]) -> Dict[str, Any]:
    """Workflow entrypoint for Documentation Agent."""
    if isinstance(input_data, dict):
        input_data = DocumentationAgentInput.model_validate(input_data)

    run_id = str(input_data.run_id)
    documents = {
        "README.md": _build_readme_markdown(input_data),
        "API_REFERENCE.md": _build_api_reference_markdown(input_data.design_spec),
        "ARCHITECTURE.md": _build_architecture_markdown(input_data),
        "KNOWN_ISSUES.md": _build_known_issues_markdown(input_data.qa_output),
        "CONTRIBUTING.md": _build_contributing_markdown(input_data),
        "CHANGELOG.md": _build_changelog_markdown(input_data),
    }

    return {
        "run_id": run_id,
        "documents": documents,
    }
