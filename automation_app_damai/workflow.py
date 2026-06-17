from automation_runner.workflows import (
    ManagedWorkflow,
    WorkflowResult,
    WorkflowStep,
    run_workflow_steps,
)


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
