from automation_runner.workflows import (
    ManagedWorkflow,
    WorkflowStep,
    run_workflow_steps,
)


def build_slider_capability_request(
    *,
    page,
    page_url: str = "",
    provider: str = "auto",
    metadata=None,
    run_id: str = None,
    task_id: str = None,
):
    from automation_core.capabilities import CapabilityRequest

    request_metadata = {}
    if run_id is not None:
        request_metadata["run_id"] = run_id
    if task_id is not None:
        request_metadata["task_id"] = task_id
    return CapabilityRequest(
        capability="visual.challenge",
        operation="solve",
        parameters={
            "challenge_type": "slider_captcha",
            "context": "playwright_page",
            "page": page,
            "page_url": page_url,
            "provider": provider,
            "metadata": dict(metadata or {}),
        },
        metadata=request_metadata,
    )


async def solve_slider_capability(
    *,
    capability_executor,
    page,
    page_url: str = "",
    provider: str = "auto",
    metadata=None,
    run_id: str = None,
    task_id: str = None,
):
    if capability_executor is None:
        return None
    request = build_slider_capability_request(
        page=page,
        page_url=page_url,
        provider=provider,
        metadata=metadata,
        run_id=run_id,
        task_id=task_id,
    )
    return await capability_executor.aexecute(request)


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


async def solve_slider_visual_challenge(
    *,
    visual_solver,
    page,
    page_url: str = "",
    provider: str = "auto",
    metadata=None,
    task_id: str = None,
    prefer_native: bool = False,
):
    if visual_solver is None:
        return None

    request = build_slider_visual_request(
        page=page,
        page_url=page_url,
        provider=provider,
        metadata=metadata,
    )
    result = await visual_solver.solve(request)
    return visual_result_to_workflow_payload(
        result,
        task_id=task_id,
        prefer_native=prefer_native,
    )


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
