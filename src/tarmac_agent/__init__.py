"""Tarmac: test your on-chain agent before it goes live.

The same typed tools as the TypeScript SDK, for Python agents. Standard library only.
"""

from ._client import RunSession, TarmacClient, TarmacTools, run_agent
from ._errors import TarmacToolError
from ._types import (
    BalanceEntry,
    BalancesResult,
    FinishResult,
    PolicyCheck,
    PolicyLimits,
    QuoteResult,
    RunContext,
    SwapResult,
    TokenInfo,
)

__all__ = [
    "__version__",
    "TarmacClient",
    "TarmacTools",
    "RunSession",
    "run_agent",
    "TarmacToolError",
    "RunContext",
    "TokenInfo",
    "PolicyLimits",
    "BalanceEntry",
    "BalancesResult",
    "QuoteResult",
    "PolicyCheck",
    "SwapResult",
    "FinishResult",
]
from ._version import __version__
