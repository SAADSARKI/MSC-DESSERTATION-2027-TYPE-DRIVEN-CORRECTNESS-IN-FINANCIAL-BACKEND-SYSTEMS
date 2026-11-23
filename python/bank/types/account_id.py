"""Account identifier: immutable and never empty."""
from dataclasses import dataclass

from bank.types.errors import InvalidAccountId


@dataclass(frozen=True)  # [ENF:I4]
class AccountId:
    value: str

    def __post_init__(self) -> None:
        if self.value == "":  # [ENF:I4]
            raise InvalidAccountId()
