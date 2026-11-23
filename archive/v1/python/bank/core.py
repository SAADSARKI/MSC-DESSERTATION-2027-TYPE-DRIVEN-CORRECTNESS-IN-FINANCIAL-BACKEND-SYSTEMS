from dataclasses import dataclass
from typing import Final

M: Final[int] = 2**64 - 1  # [ENF:I1]


class BankError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code: str = code


class InvalidAccountId(BankError):
    def __init__(self) -> None:
        super().__init__("INVALID_ACCOUNT_ID")


class DuplicateAccount(BankError):
    def __init__(self) -> None:
        super().__init__("DUPLICATE_ACCOUNT")


class AccountNotFound(BankError):
    def __init__(self) -> None:
        super().__init__("ACCOUNT_NOT_FOUND")


class InvalidAmount(BankError):
    def __init__(self) -> None:
        super().__init__("INVALID_AMOUNT")


class InsufficientFunds(BankError):
    def __init__(self) -> None:
        super().__init__("INSUFFICIENT_FUNDS")


class BalanceLimitExceeded(BankError):
    def __init__(self) -> None:
        super().__init__("BALANCE_LIMIT_EXCEEDED")


@dataclass(frozen=True)  # [ENF:I4]
class AccountId:
    value: str

    def __post_init__(self) -> None:
        if self.value == "":  # [ENF:I4]
            raise InvalidAccountId()


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


@dataclass
class TransactionRecord:
    kind: str
    account: str
    counterparty: str
    amount: int


class FinancialService:
    def __init__(self) -> None:
        self._accounts: dict[AccountId, Account] = {}
        self._records: list[TransactionRecord] = []

    def accounts(self) -> list[Account]:
        return list(self._accounts.values())

    def records(self) -> list[TransactionRecord]:
        return list(self._records)

    def create_account(self, account_id: AccountId) -> None:
        if account_id in self._accounts:  # [ENF:I4]
            raise DuplicateAccount()
        self._accounts[account_id] = Account(id=account_id, balance=0)

    def balance(self, account_id: AccountId) -> int:
        acct = self._accounts.get(account_id)
        if acct is None:  # [ENF:I4]
            raise AccountNotFound()
        return acct.balance

    def deposit(self, account_id: AccountId, amount: int) -> None:
        if amount <= 0:  # [ENF:I3]
            raise InvalidAmount()
        acct = self._accounts.get(account_id)
        if acct is None:  # [ENF:I4]
            raise AccountNotFound()
        acct.credit(amount)
        self._records.append(
            TransactionRecord("deposit", account_id.value, "", amount)
        )

    def withdraw(self, account_id: AccountId, amount: int) -> None:
        if amount <= 0:  # [ENF:I3]
            raise InvalidAmount()
        acct = self._accounts.get(account_id)
        if acct is None:  # [ENF:I4]
            raise AccountNotFound()
        acct.debit(amount)
        self._records.append(
            TransactionRecord("withdraw", account_id.value, "", amount)
        )

    def transfer(
        self, from_id: AccountId, to_id: AccountId, amount: int
    ) -> None:
        if amount <= 0:  # [ENF:I3]
            raise InvalidAmount()
        src = self._accounts.get(from_id)
        if src is None:  # [ENF:I4]
            raise AccountNotFound()
        dst = self._accounts.get(to_id)
        if dst is None:  # [ENF:I4]
            raise AccountNotFound()
        if src.balance < amount:  # [ENF:I1]
            raise InsufficientFunds()
        if dst.balance + amount > M:  # [ENF:I1]
            raise BalanceLimitExceeded()
        src.balance -= amount  # [ENF:I2]
        dst.balance += amount  # [ENF:I2]
        self._records.append(
            TransactionRecord("transfer", from_id.value, to_id.value, amount)
        )
