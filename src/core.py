from typing import Dict, Any

class RoundTableNode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.active = False

    def start(self) -> Dict[str, Any]:
        self.active = True
        return {"node_id": self.node_id, "status": "running"}

    def stop(self) -> Dict[str, Any]:
        self.active = False
        return {"node_id": self.node_id, "status": "stopped"}
