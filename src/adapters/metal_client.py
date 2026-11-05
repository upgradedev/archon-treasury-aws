"""Metal L1 testnet USDZ spend governance (Kit 11 shape, offline).

Three autonomous sub-agents pay per API call in USDZ minor units. The
treasury rule is deterministic and integer-only: a fixed total budget,
per-agent weights, and a hard call cap derived from the live per-call
price. When a price rises, that agent buys fewer calls; freed budget is
not silently re-spent by anyone. Rebalancing recomputes caps from the
weights and the new prices and reports every change. No chain call
happens without an injected transport, so tests run fully offline.
"""

from dataclasses import dataclass, field
from typing import Callable

from adapters.airwallex_client import AdapterError
from kerdon.money import Money

ChainTransport = Callable[[str, Money, str], str]  # (agent_id, amount, memo) -> tx ref


@dataclass(frozen=True, slots=True)
class AgentBudget:
    agent_id: str
    weight: int  # share of the total budget, integer points summing to 100
    price_per_call: Money  # USDZ minor units


@dataclass(slots=True)
class MetalSpendGovernor:
    total_budget: Money  # USDZ
    budgets: tuple[AgentBudget, ...]
    transport: ChainTransport
    _spent_cents: dict[str, int] = field(default_factory=dict)
    _calls: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_budget.currency != "USDZ":
            raise AdapterError("Metal budgets are denominated in USDZ")
        if sum(b.weight for b in self.budgets) != 100:
            raise AdapterError("agent weights must sum to 100")
        for b in self.budgets:
            if b.price_per_call.currency != "USDZ" or b.price_per_call.amount_cents <= 0:
                raise AdapterError(f"bad USDZ price for {b.agent_id}")

    def allowance_cents(self, agent_id: str) -> int:
        budget = self._budget(agent_id)
        return self.total_budget.amount_cents * budget.weight // 100

    def call_cap(self, agent_id: str) -> int:
        return self.allowance_cents(agent_id) // self._budget(agent_id).price_per_call.amount_cents

    def spent_cents(self, agent_id: str) -> int:
        return self._spent_cents.get(agent_id, 0)

    def pay_for_call(self, agent_id: str, memo: str) -> str:
        budget = self._budget(agent_id)
        if self._calls.get(agent_id, 0) >= self.call_cap(agent_id):
            raise AdapterError(f"{agent_id} hit its USDZ call cap; Treasury refuses the payment")
        tx = self.transport(agent_id, budget.price_per_call, memo)
        self._calls[agent_id] = self._calls.get(agent_id, 0) + 1
        self._spent_cents[agent_id] = self.spent_cents(agent_id) + budget.price_per_call.amount_cents
        return tx

    def rebalance(self, new_prices: dict[str, Money]) -> tuple[dict, ...]:
        """Recompute caps after price moves. Returns one row per change."""
        rows = []
        updated = []
        for b in self.budgets:
            new_price = new_prices.get(b.agent_id, b.price_per_call)
            if new_price.currency != "USDZ" or new_price.amount_cents <= 0:
                raise AdapterError(f"bad USDZ price for {b.agent_id}")
            old_cap = self.allowance_cents(b.agent_id) // b.price_per_call.amount_cents
            new_cap = self.allowance_cents(b.agent_id) // new_price.amount_cents
            if new_price != b.price_per_call:
                rows.append(
                    {
                        "agent_id": b.agent_id,
                        "old_price": b.price_per_call.spoken(),
                        "new_price": new_price.spoken(),
                        "old_call_cap": old_cap,
                        "new_call_cap": new_cap,
                    }
                )
            updated.append(AgentBudget(b.agent_id, b.weight, new_price))
        self.budgets = tuple(updated)
        return tuple(rows)

    def _budget(self, agent_id: str) -> AgentBudget:
        for b in self.budgets:
            if b.agent_id == agent_id:
                return b
        raise AdapterError(f"unknown sub-agent {agent_id!r}")


@dataclass(slots=True)
class FakeMetalTransport:
    payments: list[tuple[str, int, str]] = field(default_factory=list)

    def __call__(self, agent_id: str, amount: Money, memo: str) -> str:
        self.payments.append((agent_id, amount.amount_cents, memo))
        return f"mtl_fake_{len(self.payments)}"
