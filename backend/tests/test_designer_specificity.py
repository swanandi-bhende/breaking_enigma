from __future__ import annotations

import pytest

from app.agents.designer import run_designer_agent
from app.schemas.agents import (
    AcceptanceCriterion,
    BudgetEstimate,
    Feature,
    Features,
    ProductVision,
    PRD,
    UserFlowStep,
    UserStory,
)


def _build_expense_prd() -> PRD:
    return PRD(
        product_vision=ProductVision(
            elevator_pitch="Freelancer Expense Tracker",
            target_user="freelancers",
            core_value_proposition="Help freelancers track expenses, categories, and reports quickly.",
            success_definition="Users can add, categorize, and report expenses without friction.",
        ),
        user_stories=[
            UserStory(
                id="US-001",
                persona="Freelancer",
                action="add a business expense",
                outcome="the expense is saved and categorized",
                priority="must-have",
                acceptance_criteria=[
                    AcceptanceCriterion(
                        given="the user is on the expense entry screen",
                        when="they submit a valid expense",
                        then="the expense appears in their expense list",
                    )
                ],
                estimated_effort="M",
            ),
            UserStory(
                id="US-002",
                persona="Freelancer",
                action="upload a receipt",
                outcome="the receipt is attached to an expense",
                priority="should-have",
                acceptance_criteria=[
                    AcceptanceCriterion(
                        given="the user has an expense",
                        when="they upload a receipt image",
                        then="the receipt is linked to that expense",
                    )
                ],
                estimated_effort="S",
            ),
        ],
        features=Features(
            mvp=[
                Feature(
                    id="F-001",
                    name="Expense logging",
                    description="Add and save expense records with category and receipt support.",
                    maps_to_user_stories=["US-001", "US-002"],
                )
            ],
            v1_1=[],
            v2_0=[],
        ),
        budget_estimate=BudgetEstimate(
            mvp_engineer_weeks=4.0,
            mvp_cost_usd_range="$40k-$60k",
            assumptions=["Single platform", "Lean MVP"],
        ),
        user_flow=[
            UserFlowStep(
                step=1,
                screen_name="Dashboard",
                user_action="review expense summary",
                system_response="show totals and recent expenses",
                next_step=2,
            ),
            UserFlowStep(
                step=2,
                screen_name="Add Expense",
                user_action="enter a new expense",
                system_response="save the expense and refresh the dashboard",
                next_step=None,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_designer_is_prompt_specific_for_expense_tracker() -> None:
    result = await run_designer_agent({"run_id": "run-123", "prd": _build_expense_prd().model_dump(mode="json")})
    design_spec = result["design_spec"]

    screen_names = " ".join(screen["screen_name"].lower() for screen in design_spec["screens"])
    purposes = " ".join(screen["purpose"].lower() for screen in design_spec["screens"])
    component_names = " ".join(
        component["component_name"].lower()
        for screen in design_spec["screens"]
        for component in screen["components"]
    )
    entity_names = " ".join(model["entity_name"].lower() for model in design_spec["data_models"])
    api_descriptions = " ".join(endpoint["description"].lower() for endpoint in design_spec["api_spec"])
    api_paths = " ".join(endpoint["path"].lower() for endpoint in design_spec["api_spec"])
    architecture_blob = " ".join(
        str(v).lower() for v in design_spec["system_architecture"].values()
    )

    assert "expense" in screen_names
    assert "freelancer" in purposes or "freelancers" in purposes
    assert "expense" in component_names
    assert "expense" in entity_names
    assert "receipt" in api_descriptions or "report" in api_descriptions
    assert "/expenses" in api_paths
    assert "/projects" not in api_paths
    assert "expense" in architecture_blob
    assert any("expense" in flow["flow_name"].lower() for flow in design_spec["interaction_flows"])