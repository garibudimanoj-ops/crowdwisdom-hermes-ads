def pytest_collection_modifyitems(config, items):
    """Skip live integration tests by default unless -m live is specified."""
    if not config.getoption("markexpr"):
        items[:] = [item for item in items if not item.get_closest_marker("live")]