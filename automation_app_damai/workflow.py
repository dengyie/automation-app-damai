from automation_runner.workflows import (
    ManagedWorkflow,
    WorkflowStep,
    run_workflow_steps,
)


def describe_optional_capabilities(visual_solver=None):
    return {
        "visual_challenges": "enabled" if visual_solver is not None else "disabled"
    }


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
