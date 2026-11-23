"""The five operations; each state change goes through one LedgerTransaction."""
from bank.domain.account import Account
from bank.domain.record import TransactionRecord
from bank.repository.ledger import Ledger
from bank.types.account_id import AccountId
from bank.types.errors import (
    BalanceLimitExceeded,
    DuplicateAccount,
    InsufficientFunds,
    InvalidAmount,
)
from bank.types.money import M


class FinancialService:
    def __init__(self) -> None:
        self._ledger = Ledger()

    def accounts(self) -> list[Account]:
        return self._ledger.accounts()

    def records(self) -> list[TransactionRecord]:
        return self._ledger.records()

    def create_account(self, account_id: AccountId) -> None:
        if self._ledger.contains(account_id):  # [ENF:I4]
            raise DuplicateAccount()
        txn = self._ledger.begin()
        txn.save(Account(id=account_id, balance=0))
        txn.commit()

    def balance(self, account_id: AccountId) -> int:
        return self._ledger.find(account_id).balance

    def deposit(self, account_id: AccountId, amount: int) -> None:
        if amount <= 0:  # [ENF:I3]
            raise InvalidAmount()
        txn = self._ledger.begin()
        acct = txn.load(account_id)
        acct.credit(amount)
        txn.save(acct)
        txn.record(TransactionRecord("deposit", account_id.value, "", amount))
        txn.commit()

    def withdraw(self, account_id: AccountId, amount: int) -> None:
        if amount <= 0:  # [ENF:I3]
            raise InvalidAmount()
        txn = self._ledger.begin()
        acct = txn.load(account_id)
        acct.debit(amount)
        txn.save(acct)
        txn.record(TransactionRecord("withdraw", account_id.value, "", amount))
        txn.commit()

    def transfer(self, from_id: AccountId, to_id: AccountId, amount: int) -> None:
        if amount <= 0:  # [ENF:I3]
            raise InvalidAmount()
        txn = self._ledger.begin()
        src = txn.load(from_id)
        dst = txn.load(to_id)
        if src.balance < amount:  # [ENF:I1]
            raise InsufficientFunds()
        if dst.balance + amount > M:  # [ENF:I1]
            raise BalanceLimitExceeded()
        src.balance -= amount  # [ENF:I2]
        dst.balance += amount  # [ENF:I2]
        txn.save(src)
        txn.save(dst)
        txn.record(TransactionRecord("transfer", from_id.value, to_id.value, amount))
        txn.commit()
