"""Shapes returned by the Tarmac tools. Amounts are decimal strings of integer base units."""

from typing import List, Literal, Optional, TypedDict


class TokenInfo(TypedDict):
    symbol: str
    address: str
    decimals: int


class PolicyLimits(TypedDict):
    version: str
    maxSlippageBps: int
    spendCap: str
    deadlineSeconds: int
    slippageReference: str


class RunContext(TypedDict):
    runId: str
    mode: Literal["fixture", "fork"]
    instruction: str
    chain: dict
    venue: dict
    wallet: dict
    tokenIn: TokenInfo
    tokenOut: TokenInfo
    amountIn: str
    policy: PolicyLimits


class BalanceEntry(TypedDict):
    symbol: str
    address: str
    decimals: int
    raw: str
    formatted: str


class BalancesResult(TypedDict):
    wallet: str
    block: Optional[str]
    balances: List[BalanceEntry]


class QuoteResult(TypedDict):
    quoteId: str
    tokenIn: str
    tokenOut: str
    amountIn: str
    amountOut: str
    venue: dict
    reference: dict
    slippageBps: int
    policy: dict
    block: Optional[str]
    expiresAt: str


class PolicyCheck(TypedDict):
    id: str
    label: str
    passed: bool
    expected: str
    actual: str


class SwapResult(TypedDict, total=False):
    status: Literal["executed", "blocked", "failed"]
    checks: List[PolicyCheck]
    reason: str
    execution: dict


class FinishResult(TypedDict):
    runId: str
    status: str
    verdict: Optional[Literal["executed", "stopped", "blocked", "failed"]]
