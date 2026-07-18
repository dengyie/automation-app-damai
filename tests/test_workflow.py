import asyncio
import inspect
from pathlib import Path

import pytest

from automation_core.drivers import ActionResult, ArtifactHandle, SessionInfo
from automation_runner import WorkflowContext, WorkflowOptions
from automation_app_damai.workflow import (
    build_composition_root,
    build_slider_capability_request,
    create_capability_steps,
    create_workflow,
)


class FakeSession:
    def __init__(self):
        self.info = SessionInfo(
            driver_name="fake-damai",
            platform="web",
            identifier="damai-app",
        )
        self.actions = []

    def start(self):
        return None

    def stop(self):
        return None

    def execute_action(self, action_name, **kwargs):
        self.actions.append((action_name, kwargs))
        return ActionResult(success=True, message=action_name, data=kwargs)

    def capture_artifact(self, artifact_type, name):
        return ArtifactHandle(artifact_type=artifact_type, path=Path(name))


def test_create_workflow_uses_public_automation_runner_contract():
    session = FakeSession()
    workflow = create_workflow(
        session_factory=lambda: session,
        context=WorkflowContext(workflow_name="damai-web", live=False),
        options=WorkflowOptions(url="https://example.test/damai"),
    )

    result = workflow.run()

    assert workflow.name == "damai-web"
    assert result.success is True
    assert result.steps[0].action_result.message == "open"


def test_build_slider_capability_request_uses_platform_contract_only():
    page = object()
    request = build_slider_capability_request(
        page=page,
        page_url="https://example.test/damai",
        provider="auto",
        metadata={"cookie_id": "damai-user"},
    )

    assert request.capability == "visual.challenge"
    assert request.operation == "solve"
    assert request.parameters["challenge_type"] == "slider_captcha"
    assert request.parameters["context"] == "playwright_page"
    assert request.parameters["page"] is page
    assert request.parameters["metadata"]["cookie_id"] == "damai-user"


def test_create_capability_steps_uses_platform_request_contract():
    steps = create_capability_steps(page="page", page_url="https://example.test")

    assert steps[0].kind == "capability"
    assert steps[0].request.parameters["page"] == "page"


def test_damai_capability_runs_through_platform_executor_and_slidex_adapter():
    pytest.importorskip("slidex")
    from automation_core.capabilities import CapabilityExecutionProfile, CapabilityResult
    from slidex.integrations.automation_kit import SlidexVisualCapability
    from slidex.vision import VisualChallengeResult

    class FakeVisualSolver:
        async def solve(self, request):
            assert request.metadata["run_id"] == "run-1"
            assert request.metadata["task_id"]
            return VisualChallengeResult(
                success=True,
                challenge_type=request.challenge_type,
                provider="fake-slider",
            )

    session = FakeSession()
    runtime = build_composition_root(
        session_factory=lambda: session,
        provider=SlidexVisualCapability(visual_solver=FakeVisualSolver()),
        workflow_name="damai-web",
    )
    runtime.run_id = "run-1"
    result = runtime.run(
        create_capability_steps(page="page")
    )

    assert result.success is True
    assert result.steps[0].capability_result.provider == "slidex"
    assert result.steps[0].capability_result.metadata["visual_provider"] == "fake-slider"


def test_damai_workflow_exposes_only_generic_visual_capability_surface():
    import automation_app_damai.workflow as module

    assert "visual_solver" not in inspect.signature(module.create_workflow).parameters
    for retired_name in [
        "describe_optional_capabilities",
        "build_slider_visual_request",
        "visual_result_to_workflow_payload",
        "solve_slider_visual_challenge",
        "solve_slider_capability",
    ]:
        assert not hasattr(module, retired_name)
