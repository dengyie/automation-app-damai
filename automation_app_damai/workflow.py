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


def create_workflow(session_factory, context, options) -> ManagedWorkflow:
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
