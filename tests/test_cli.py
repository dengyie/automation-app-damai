from automation_app_damai.cli import build_context_and_options


def test_cli_builds_runner_context_and_options():
    context, options = build_context_and_options(
        workflow_name="damai-web",
        live=False,
        url="https://example.test/damai",
        app_id=None,
    )

    assert context.workflow_name == "damai-web"
    assert context.live is False
    assert options.url == "https://example.test/damai"
    assert options.app_id is None
