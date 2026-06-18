from automation_runner.workflows import (
    ManagedWorkflow,
    WorkflowStep,
    run_workflow_steps,
)


def describe_optional_capabilities(visual_solver=None):
    return {
        "visual_challenges": "enabled" if visual_solver is not None else "disabled"
    }


def build_slider_visual_request(
    *,
    page,
    page_url: str = "",
    provider: str = "auto",
    metadata=None,
):
    from slidex.vision import ChallengeType, VisionContext, VisualChallengeRequest

    return VisualChallengeRequest(
        challenge_type=ChallengeType.SLIDER_CAPTCHA,
        context=VisionContext.PLAYWRIGHT_PAGE,
        page=page,
        page_url=page_url,
        provider=provider,
        metadata=dict(metadata or {}),
    )


def visual_result_to_workflow_payload(
    result,
    *,
    task_id: str = None,
    prefer_native: bool = False,
):
    from slidex.integrations.automation_kit import (
        to_action_result,
        to_artifacts,
        to_events,
    )

    return {
        "action": to_action_result(result, prefer_native=prefer_native),
        "artifacts": to_artifacts(result, prefer_native=prefer_native),
        "events": to_events(result, task_id=task_id, prefer_native=prefer_native),
    }


def create_workflow(session_factory, context, options, visual_solver=None) -> ManagedWorkflow:
    return ManagedWorkflow(
        name=context.workflow_name,
        session_factory=session_factory,
        run_fn=lambda session: run_workflow_steps(
            session,
            [
                WorkflowStep.action(
                    "open",
                    url=options.url or "https://example.test/damai",
                ),
                WorkflowStep.artifact("screenshot", "landing.png"),
            ],
        ),
    )
