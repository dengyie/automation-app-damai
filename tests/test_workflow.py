from pathlib import Path

from automation_core.drivers import ActionResult, ArtifactHandle, SessionInfo
from automation_runner import WorkflowContext, WorkflowOptions
from automation_app_damai.workflow import create_workflow, describe_optional_capabilities


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


def test_damai_workflow_reports_optional_capability_flag():
    assert describe_optional_capabilities()["ocr"] == "disabled"


def test_damai_workflow_can_report_optional_ocr_capability():
    from automation_plugin_ocr.fake import FakeOcrExtractor

    capabilities = describe_optional_capabilities(ocr=FakeOcrExtractor(text="ok"))

    assert capabilities["ocr"] == "enabled"
