"""One entry of the transaction history."""
from dataclasses import dataclass


@dataclass
class TransactionRecord:
    kind: str
    account: str
    counterparty: str
    amount: int
