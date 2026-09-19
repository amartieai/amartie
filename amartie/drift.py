import json
from pathlib import Path


class DriftMap:
    """Minimal attention-drift map for visual or audit overlay."""

    def __init__(self, nodes=None):
        self.nodes = nodes or [0.0 for _ in range(12)]

    def feed(self, index, amount=0.15):
        if 0 <= index < len(self.nodes):
            self.nodes[index] = min(1.0, self.nodes[index] + amount)

    def decay(self, amount=0.01):
        self.nodes = [max(0.0, n - amount) for n in self.nodes]

    def hottest(self):
        if not self.nodes:
            return None
        return max(range(len(self.nodes)), key=lambda i: self.nodes[i])

    def dump(self, path="drift.json"):
        Path(path).write_text(json.dumps({"nodes": self.nodes}, indent=2), encoding="utf-8")
        return path
