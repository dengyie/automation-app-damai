import asyncio
import inspect
from pathlib import Path

import pytest

from automation_core.drivers import ActionResult, ArtifactHandle, SessionInfo
from automation_runner import WorkflowContext, WorkflowOptions
from automation_app_damai.workflow import (
    build_slider_capability_request,
    create_workflow,
    solve_slider_capability,
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
    assert result.actions[0].message == "open"


def test_build_slider_capability_request_uses_platform_contract_only():
    page = object()
    request = build_slider_capability_request(
        page=page,
        page_url="https://example.test/damai",
        provider="auto",
        metadata={"cookie_id": "damai-user"},
        run_id="run-1",
        task_id="task-1",
    )

    assert request.capability == "visual.challenge"
    assert request.operation == "solve"
    assert request.parameters["challenge_type"] == "slider_captcha"
    assert request.parameters["context"] == "playwright_page"
    assert request.parameters["page"] is page
    assert request.parameters["metadata"]["cookie_id"] == "damai-user"
    assert request.metadata == {"run_id": "run-1", "task_id": "task-1"}


def test_solve_slider_capability_returns_none_without_executor():
    result = asyncio.run(
        solve_slider_capability(capability_executor=None, page=object())
    )

    assert result is None


def test_solve_slider_capability_calls_async_platform_executor():
    class FakeExecutor:
        def __init__(self):
            self.requests = []

        async def aexecute(self, request):
            self.requests.append(request)
            from automation_core.capabilities import CapabilityResult

            return CapabilityResult(success=True, provider="fake")

    executor = FakeExecutor()
    result = asyncio.run(
        solve_slider_capability(
            capability_executor=executor,
            page="page",
            task_id="task-1",
        )
    )

    assert result.success is True
    assert executor.requests[0].parameters["page"] == "page"
    assert executor.requests[0].metadata["task_id"] == "task-1"


def test_damai_capability_runs_through_platform_executor_and_slidex_adapter():
    pytest.importorskip("slidex")
    from automation_core.capabilities import CapabilityExecutor, CapabilityRegistry
    from slidex.integrations.automation_kit import SlidexVisualCapability
    from slidex.vision import VisualChallengeResult

    class FakeVisualSolver:
        async def solve(self, request):
            assert request.metadata["run_id"] == "run-1"
            assert request.metadata["task_id"] == "task-1"
            return VisualChallengeResult(
                success=True,
                challenge_type=request.challenge_type,
                provider="fake-slider",
            )

    registry = CapabilityRegistry()
    registry.register(SlidexVisualCapability(visual_solver=FakeVisualSolver()))
    result = asyncio.run(
        solve_slider_capability(
            capability_executor=CapabilityExecutor(registry),
            page="page",
            run_id="run-1",
            task_id="task-1",
        )
    )

    assert result.success is True
    assert result.provider == "slidex"
    assert result.metadata["visual_provider"] == "fake-slider"


def test_damai_workflow_exposes_only_generic_visual_capability_surface():
    import automation_app_damai.workflow as module

    assert "visual_solver" not in inspect.signature(module.create_workflow).parameters
    for retired_name in [
        "describe_optional_capabilities",
        "build_slider_visual_request",
        "visual_result_to_workflow_payload",
        "solve_slider_visual_challenge",
    ]:
        assert not hasattr(module, retired_name)
