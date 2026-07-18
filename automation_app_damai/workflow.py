from automation_core.capabilities import (
    CapabilityExecutor,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResolver,
)
from automation_runner.policies import CapabilityPolicy
from automation_runner.runtime import WorkflowRuntime
from automation_runner.steps import WorkflowStep


def build_slider_capability_request(
    *,
    page,
    page_url: str = "",
    provider: str = "auto",
    metadata=None,
):
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
    )


def build_composition_root(
    *,
    session_factory,
    provider=None,
    workflow_name: str = "damai-web",
):
    registry = CapabilityRegistry()
    if provider is not None:
        registry.register(provider)
    resolver = CapabilityResolver(registry)
    executor = CapabilityExecutor(resolver)
    return WorkflowRuntime(
        session_factory=session_factory,
        capability_executor=executor,
        workflow_name=workflow_name,
    )


class ComposedWorkflow:
    def __init__(self, runtime, steps):
        self.runtime = runtime
        self.steps = steps
        self.name = runtime.workflow_name

    def run(self):
        return self.runtime.run(self.steps)


def create_workflow(session_factory, context, options):
    runtime = build_composition_root(
        session_factory=session_factory,
        workflow_name=context.workflow_name,
    )
    steps = [
        WorkflowStep.action(
            "open",
            url=options.url or "https://example.test/damai",
        )
    ]
    return ComposedWorkflow(runtime, steps)


def create_capability_steps(*, page, page_url: str = "", provider: str = "auto"):
    return [
        WorkflowStep.capability(
            "solve-slider",
            request=build_slider_capability_request(
                page=page,
                page_url=page_url,
                provider=provider,
            ),
            policy=CapabilityPolicy(timeout=30.0, max_attempts=1, backoff=0.0),
        )
    ]
