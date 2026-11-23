"""Account entity. There is no default balance."""
from dataclasses import dataclass

from bank.types.account_id import AccountId
from bank.types.errors import BalanceLimitExceeded, InsufficientFunds
from bank.types.money import M


@dataclass
class Account:
    id: AccountId
    balance: int

    def debit(self, amount: int) -> None:
        if self.balance < amount:  # [ENF:I1]
            raise InsufficientFunds()
        self.balance -= amount

    def credit(self, amount: int) -> None:
        if self.balance + amount > M:  # [ENF:I1]
            raise BalanceLimitExceeded()
        self.balance += amount
