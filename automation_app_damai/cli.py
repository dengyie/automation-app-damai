from automation_runner import WorkflowContext, WorkflowOptions


def build_context_and_options(workflow_name, live, url, app_id):
    return (
        WorkflowContext(workflow_name=workflow_name, live=live),
        WorkflowOptions(url=url, app_id=app_id),
    )
