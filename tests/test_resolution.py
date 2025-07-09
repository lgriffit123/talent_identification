from etl import entity_resolution


def test_resolve_entities_identity():
    sample = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    resolved = entity_resolution.resolve_entities(sample)

    # Placeholder test: ensures the function returns a list of same length.
    assert isinstance(resolved, list)
    assert len(resolved) == len(sample) 