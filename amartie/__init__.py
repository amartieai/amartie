"""
AMARTIE — The Open-Source AI Security Framework

Receipts, not promises. Every AI response verified by 9 judges.
Hash-chained receipts prove the model wasn't swapped.

Modules:
    gate        — 9-judge verification gate with rotating IDs
    receipt     — Hash-chained receipt system
    sandbox     — Kernel containment (snapshot/diff/quarantine)
    vault       — Encrypted tool vaults + swarm tasks + anti-tamper
"""

__version__ = "0.1.0"
__author__ = "AMARTIE Contributors"

from .gate import JudgeGate, JudgeVerdict, GateReceipt, gate
from .receipt import Receipt, ReceiptChain
from .sandbox import Sandbox, Snapshot, sandbox
from .vault import Vault, SwarmTask, AntiTamper

__all__ = [
    "JudgeGate",
    "JudgeVerdict", 
    "GateReceipt",
    "gate",
    "Receipt",
    "ReceiptChain",
    "Sandbox",
    "Snapshot",
    "sandbox",
    "Vault",
    "SwarmTask",
    "AntiTamper",
    "__version__",
]
