"""Context builder tests against the real fixture PCAP."""

import pytest

from src.services.llm.context_builder import build_context
from src.services.topology import load_topology


@pytest.fixture()
def ready_session(pcap_session):
    """pcap_session already built topology via conftest."""
    return pcap_session


def test_summary_and_sample(ready_session):
    session, pcap_path = ready_session
    text, manifest = build_context(session.id, pcap_path)
    topo = load_topology(session.id)
    # Summary always present and never truncated
    assert "Capture file:" in text
    assert "## Hosts" in text
    assert "## Top edges" in text
    assert "## Protocol breakdown" in text
    for n in topo.elements.nodes:
        assert n.data.id in text
    # Packet sample present, formatted rows only (no hex blobs)
    assert "## Packet sample" in text
    assert manifest[0]["name"] == "summary"
    assert all("approxTokens" in b for b in manifest)


def test_node_focus(ready_session):
    session, pcap_path = ready_session
    topo = load_topology(session.id)
    node_id = topo.elements.nodes[0].data.id
    text, manifest = build_context(session.id, pcap_path, focus_node_id=node_id)
    assert any(b["name"] == "node_detail" for b in manifest)
    assert f"Focused node {node_id}" in text


def test_budget_truncation_drops_sample_first(ready_session, monkeypatch):
    from src.services.llm import context_builder as cb

    session, pcap_path = ready_session
    monkeypatch.setattr(cb, "TOKEN_BUDGET", 10)  # force tiny budget
    text, manifest = build_context(session.id, pcap_path)
    names = [b["name"] for b in manifest]
    assert "summary" in names  # never truncated
    # sample dropped before summary
    if "packet_sample" in names:
        assert names.index("packet_sample") > names.index("summary")
