"""pskovedu.auth.solvers — pluggable challenge solver implementations."""

from __future__ import annotations

from .base import ChallengeSolver
from .qr import QrSolver

__all__ = ["ChallengeSolver", "QrSolver"]
