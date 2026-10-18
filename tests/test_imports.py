def test_app_package_imports():
    from automation_app_damai import __version__

    assert __version__ == "0.3.0"
