import pytest
from src.core import RoundTableNode

def test_node_lifecycle():
    node = RoundTableNode(node_id="worker-01")
    assert not node.active

    res_start = node.start()
    assert res_start["status"] == "running"
    assert node.active is True

    res_stop = node.stop()
    assert res_stop["status"] == "stopped"
    assert node.active is False
