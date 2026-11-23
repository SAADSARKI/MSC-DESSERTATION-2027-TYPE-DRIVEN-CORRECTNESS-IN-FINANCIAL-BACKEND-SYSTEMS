"""One exception class per error code of the specification."""


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
