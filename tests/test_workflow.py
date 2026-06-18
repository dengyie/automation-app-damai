import json
from pathlib import Path

import pytest

from automation_core.drivers import ActionResult, ArtifactHandle, SessionInfo
from automation_runner import WorkflowContext, WorkflowOptions
from automation_app_damai.workflow import (
    build_slider_visual_request,
    create_workflow,
    describe_optional_capabilities,
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
