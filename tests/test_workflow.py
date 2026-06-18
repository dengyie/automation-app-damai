import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

from automation_core.drivers import ActionResult, ArtifactHandle, SessionInfo
from automation_runner import WorkflowContext, WorkflowOptions
from automation_app_damai.workflow import (
    build_slider_visual_request,
    create_workflow,
    describe_optional_capabilities,
    solve_slider_visual_challenge,
    visual_result_to_workflow_payload,
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


def test_damai_workflow_reports_visual_capability_flag():
    assert describe_optional_capabilities()["visual_challenges"] == "disabled"


def test_damai_workflow_can_report_optional_slidex_visual_capability():
    class FakeVisualSolver:
        pass

    capabilities = describe_optional_capabilities(visual_solver=FakeVisualSolver())

    assert capabilities["visual_challenges"] == "enabled"


def test_create_workflow_accepts_visual_solver_without_changing_offline_flow():
    class FakeVisualSolver:
        pass

    session = FakeSession()
    workflow = create_workflow(
        session_factory=lambda: session,
        context=WorkflowContext(workflow_name="damai-web", live=False),
        options=WorkflowOptions(url="https://example.test/damai"),
        visual_solver=FakeVisualSolver(),
    )

    result = workflow.run()

    assert result.success is True
    assert session.actions[0][0] == "open"


def test_build_slider_visual_request_uses_slidex_playwright_page_contract():
    pytest.importorskip("slidex")

    page = object()
    request = build_slider_visual_request(
        page=page,
        page_url="https://example.test/damai",
        provider="auto",
        metadata={"cookie_id": "damai-user"},
    )

    from slidex.vision import ChallengeType, VisionContext

    assert request.challenge_type == ChallengeType.SLIDER_CAPTCHA
    assert request.context == VisionContext.PLAYWRIGHT_PAGE
    assert request.page is page
    assert request.metadata["cookie_id"] == "damai-user"


def test_visual_result_to_workflow_payload_returns_json_safe_shapes():
    pytest.importorskip("slidex")

    from pathlib import Path
    from slidex.vision import ChallengeType, VisionArtifact, VisualChallengeResult

    result = VisualChallengeResult(
        success=True,
        challenge_type=ChallengeType.SLIDER_CAPTCHA,
        provider="fake",
        artifacts=[
            VisionArtifact(
                artifact_type="telemetry",
                path=Path("artifacts/run-1/telemetry/events.jsonl"),
                metadata={"token": "secret"},
            )
        ],
    )

    payload = visual_result_to_workflow_payload(result, task_id="task-1")

    assert payload["action"]["success"] is True
    assert payload["artifacts"][0]["path"] == "artifacts/run-1/telemetry/events.jsonl"
    assert payload["artifacts"][0]["metadata"]["token"] == "[redacted]"
    assert payload["events"][-1]["event_type"] == "task.end"
    json.dumps(payload)


def test_solve_slider_visual_challenge_uses_lazy_slidex_helpers_without_dependency(monkeypatch):
    slidex = types.ModuleType("slidex")
    vision = types.ModuleType("slidex.vision")
    integrations = types.ModuleType("slidex.integrations")
    automation_kit = types.ModuleType("slidex.integrations.automation_kit")

    class ChallengeType:
        SLIDER_CAPTCHA = "slider_captcha"

    class VisionContext:
        PLAYWRIGHT_PAGE = "playwright_page"

    class VisualChallengeRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    vision.ChallengeType = ChallengeType
    vision.VisionContext = VisionContext
    vision.VisualChallengeRequest = VisualChallengeRequest
    automation_kit.to_action_result = lambda result, prefer_native=False: {
        "success": result["success"]
    }
    automation_kit.to_artifacts = lambda result, prefer_native=False: []
    automation_kit.to_events = lambda result, task_id=None, prefer_native=False: [
        {"event_type": "task.end", "task_id": task_id, "payload": result}
    ]

    monkeypatch.setitem(sys.modules, "slidex", slidex)
    monkeypatch.setitem(sys.modules, "slidex.vision", vision)
    monkeypatch.setitem(sys.modules, "slidex.integrations", integrations)
    monkeypatch.setitem(
        sys.modules,
        "slidex.integrations.automation_kit",
        automation_kit,
    )

    class FakeVisualSolver:
        async def solve(self, request):
            assert request.context == VisionContext.PLAYWRIGHT_PAGE
            assert request.page == "page"
            return {"success": True}

    payload = asyncio.run(
        solve_slider_visual_challenge(
            visual_solver=FakeVisualSolver(),
            page="page",
            task_id="task-1",
        )
    )

    assert payload["action"]["success"] is True
    assert payload["events"][0]["task_id"] == "task-1"


def test_solve_slider_visual_challenge_calls_slidex_solver_and_returns_payload():
    pytest.importorskip("slidex")

    from slidex.vision import ChallengeType, VisualChallengeResult

    class FakeVisualSolver:
        def __init__(self):
            self.requests = []

        async def solve(self, request):
            self.requests.append(request)
            return VisualChallengeResult(
                success=True,
                challenge_type=request.challenge_type,
                provider="fake",
                metadata={"page_url": request.page_url},
            )

    page = object()
    solver = FakeVisualSolver()

    payload = asyncio.run(
        solve_slider_visual_challenge(
            visual_solver=solver,
            page=page,
            page_url="https://example.test/damai",
            task_id="visual-1",
            metadata={"cookie_id": "damai-user"},
        )
    )

    assert solver.requests[0].challenge_type == ChallengeType.SLIDER_CAPTCHA
    assert solver.requests[0].page is page
    assert solver.requests[0].metadata["cookie_id"] == "damai-user"
    assert payload["action"]["success"] is True
    assert payload["events"][-1]["payload"]["metadata"]["page_url"] == "https://example.test/damai"


def test_solve_slider_visual_challenge_returns_none_without_solver():
    payload = asyncio.run(
        solve_slider_visual_challenge(
            visual_solver=None,
            page=object(),
        )
    )

    assert payload is None
