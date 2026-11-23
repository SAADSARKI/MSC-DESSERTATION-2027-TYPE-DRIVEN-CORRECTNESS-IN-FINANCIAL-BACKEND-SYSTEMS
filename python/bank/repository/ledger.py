"""In-memory ledger and its unit of work (the role of a database transaction)."""
from __future__ import annotations

from dataclasses import replace

from bank.domain.account import Account
from bank.domain.record import TransactionRecord
from bank.types.account_id import AccountId
from bank.types.errors import AccountNotFound


class Ledger:
    """Store of accounts and records; written only by LedgerTransaction.commit."""

    def __init__(self) -> None:
        self._accounts: dict[AccountId, Account] = {}
        self._records: list[TransactionRecord] = []

    def accounts(self) -> list[Account]:
        return list(self._accounts.values())

    def records(self) -> list[TransactionRecord]:
        return list(self._records)

    def contains(self, account_id: AccountId) -> bool:
        return account_id in self._accounts

    def find(self, account_id: AccountId) -> Account:
        acct = self._accounts.get(account_id)
        if acct is None:  # [ENF:I4]
            raise AccountNotFound()
        return acct

    def begin(self) -> LedgerTransaction:
        return LedgerTransaction(self)

    def put(self, account: Account) -> None:
        self._accounts[account.id] = account

    def append(self, record: TransactionRecord) -> None:
        self._records.append(record)


class LedgerTransaction:
    """Stages changes; commit() applies them together, otherwise nothing changes."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._accounts: list[Account] = []
        self._records: list[TransactionRecord] = []

    def load(self, account_id: AccountId) -> Account:
        return replace(self._ledger.find(account_id))

    def save(self, account: Account) -> None:
        self._accounts.append(account)

    def record(self, record: TransactionRecord) -> None:
        self._records.append(record)

    def commit(self) -> None:
        for account in self._accounts:
            self._ledger.put(account)
        for record in self._records:
            self._ledger.append(record)
