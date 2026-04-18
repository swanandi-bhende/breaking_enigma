"""
DevOps Agent — Infrastructure and deployment configuration generator.

Generates Dockerfile, docker-compose, CI/CD workflows, and env templates
based on the generated code's tech stack.

Entry-point: run_devops_agent(input_dict: dict) -> dict
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agents import (
    DevOpsAgentInput,
    DevOpsAgentOutput,
    DeploymentArtifact,
    ArtifactType,
    EnvVariable,
)

from app.schemas.agents import DevOpsAgentInput

logger = logging.getLogger(__name__)

DEVOPS_SYSTEM_PROMPT = """\
You are the DevOps Agent in an autonomous product development system.
Your role is to generate complete deployment configuration for the application.

## Your Responsibilities:
1. **Infer Tech Stack** - Analyse generated files to understand services used
2. **Generate Dockerfiles** - One per service (backend, frontend, workers)
3. **Generate docker-compose.yml** - All services with networking and volumes
4. **Generate CI/CD Pipeline** - GitHub Actions workflow (test, build, deploy)
5. **Generate .env.template** - All required environment variables

## Output Requirements:
You MUST respond with ONLY a valid JSON object. No markdown, no explanations.

OUTPUT SCHEMA:
{
  "deployment_artifacts": [
    {
      "path": "Dockerfile",
      "type": "dockerfile|compose|ci_workflow|env_template|config",
      "content": "full file content here"
    }
  ],
  "startup_commands": [
    "docker-compose up -d",
    "docker-compose exec backend alembic upgrade head"
  ],
  "environment_variables": [
    {
      "key": "DATABASE_URL",
      "description": "PostgreSQL connection string",
      "required": true,
      "example_value": "postgresql+asyncpg://user:pass@localhost/dbname"
    }
  ],
  "health_check_urls": [
    "http://localhost:8000/health",
    "http://localhost:3000"
  ],
  "deployment_url": null
}
"""


async def run_devops_agent(input_dict: dict) -> dict:
    """
    Main entry-point for DevOps Agent.
    Accepts a plain dict (from executor), returns a plain dict.
    """
    input_data = DevOpsAgentInput.model_validate(input_dict)
    run_id = str(input_data.run_id)

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(run_id, "devops", "Generating deployment configuration...")
    except Exception:
        pass

    dev_output = input_data.developer_output
    dev_dict = dev_output.model_dump() if hasattr(dev_output, "model_dump") else dev_output

    files = dev_dict.get("files_created", [])
    target = getattr(input_data.deployment_target, "value", "docker-local")

    # Infer tech stack from files
    languages = list(set(f.get("language", "python") for f in files if f.get("language")))
    has_python = any(l in ["python"] for l in languages)
    has_js = any(l in ["javascript", "typescript"] for l in languages)

    file_summary = "\n".join([
        f"- {f.get('path', '')}: {f.get('purpose', '')}"
        for f in files[:15]
    ])

    user_prompt = f"""## Application Tech Stack:
Languages detected: {languages or ['python']}
Has Python backend: {has_python}
Has JS/TS frontend: {has_js}
Deployment target: {target}

## Generated Files:
{file_summary}

## Developer Summary:
{dev_dict.get('summary', 'Full-stack web application')}

## Instructions:
Generate complete deployment configuration including:
1. Dockerfile for Python backend service
2. Dockerfile for frontend (if JS/TS files detected)
3. docker-compose.yml with all services (backend, frontend, postgres, redis)
4. .github/workflows/ci.yml GitHub Actions pipeline
5. .env.template with all required variables

Return ONLY the JSON object as specified. Make the docker-compose work out-of-the-box.
"""

    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    max_retries = 2
    raw_data = None

    for attempt in range(max_retries):
        try:
            try:
                from app.core.redis import publish_log_line
                await publish_log_line(run_id, "devops", f"Generating infrastructure config (attempt {attempt + 1})...")
            except Exception:
                pass

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": DEVOPS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=5000,
            )

            raw = response.choices[0].message.content or "{}"
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

            raw_data = json.loads(text)
            break

        except Exception as e:
            logger.warning(f"DevOps attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"DevOps agent failed: {e}")

    if not raw_data:
        # Fallback: generate minimal valid docker config inline
        raw_data = _generate_fallback_config(has_python, has_js)

    # Build Pydantic output
    type_map = {
        "dockerfile": ArtifactType.DOCKERFILE,
        "compose": ArtifactType.COMPOSE,
        "ci_workflow": ArtifactType.CI_WORKFLOW,
        "env_template": ArtifactType.ENV_TEMPLATE,
        "config": ArtifactType.CONFIG,
    }

    artifacts = []
    for art in raw_data.get("deployment_artifacts", []):
        try:
            art_type = type_map.get(art.get("type", "config"), ArtifactType.CONFIG)
            artifacts.append(DeploymentArtifact(
                path=str(art.get("path", "config")),
                type=art_type,
                content=str(art.get("content", "")),
            ))
        except Exception as e:
            logger.warning(f"Skipping invalid artifact: {e}")

    env_vars = []
    for ev in raw_data.get("environment_variables", []):
        try:
            env_vars.append(EnvVariable(
                key=str(ev.get("key", "")),
                description=str(ev.get("description", "")),
                required=bool(ev.get("required", True)),
                example_value=ev.get("example_value"),
            ))
        except Exception as e:
            logger.warning(f"Skipping invalid env var: {e}")

    try:
        from app.core.redis import publish_log_line
        await publish_log_line(run_id, "devops", f"Generated {len(artifacts)} deployment artifacts ✓")
    except Exception:
        pass

    output = DevOpsAgentOutput(
        run_id=input_data.run_id,
        deployment_artifacts=artifacts,
        startup_commands=raw_data.get("startup_commands", ["docker-compose up -d"]),
        environment_variables=env_vars,
        health_check_urls=raw_data.get("health_check_urls", ["http://localhost:8000/health"]),
        deployment_url=raw_data.get("deployment_url"),
    )

    return output.model_dump(mode="json")


def _generate_fallback_config(has_python: bool, has_js: bool) -> Dict[str, Any]:
    """Generate minimal deployment config when LLM fails."""
    artifacts = []

    artifacts.append({
        "path": "Dockerfile",
        "type": "dockerfile",
        "content": """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
    })

    artifacts.append({
        "path": "docker-compose.yml",
        "type": "compose",
        "content": """version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app_password
      POSTGRES_DB: app_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
""",
    })

    artifacts.append({
        "path": ".env.template",
        "type": "env_template",
        "content": """DATABASE_URL=postgresql+asyncpg://app:app_password@postgres:5432/app_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me-in-production
""",
    })

    artifacts.append({
        "path": ".github/workflows/ci.yml",
        "type": "ci_workflow",
        "content": """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
""",
    })

    return {
        "deployment_artifacts": artifacts,
        "startup_commands": [
            "cp .env.template .env",
            "docker-compose up -d",
            "docker-compose exec backend alembic upgrade head",
        ],
        "environment_variables": [
            {"key": "DATABASE_URL", "description": "PostgreSQL URL", "required": True, "example_value": "postgresql+asyncpg://user:pass@localhost/db"},
            {"key": "REDIS_URL", "description": "Redis URL", "required": True, "example_value": "redis://localhost:6379/0"},
            {"key": "SECRET_KEY", "description": "App secret key", "required": True, "example_value": "your-secret-key"},
        ],
        "health_check_urls": ["http://localhost:8000/health"],
        "deployment_url": None,
    }
