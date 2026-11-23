import csv
import json
import sys

from bank.core import AccountId, BankError, FinancialService


def main() -> None:
    path = sys.argv[1]
    service = FinancialService()
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for step, row in enumerate(reader):
            op = row["op"]
            status = "ok"
            error: str | None = None
            value: int | None = None
            try:
                if op == "create":
                    service.create_account(AccountId(row["account"]))
                elif op == "balance":
                    value = service.balance(AccountId(row["account"]))
                elif op == "deposit":
                    service.deposit(
                        AccountId(row["account"]), int(row["amount"])
                    )
                elif op == "withdraw":
                    service.withdraw(
                        AccountId(row["account"]), int(row["amount"])
                    )
                elif op == "transfer":
                    service.transfer(
                        AccountId(row["account"]),
                        AccountId(row["to"]),
                        int(row["amount"]),
                    )
                else:
                    raise ValueError("unknown operation: " + op)
            except BankError as e:
                status = "error"
                error = e.code
            accounts = sorted(service.accounts(), key=lambda a: a.id.value)
            records = service.records()
            last: list[str | int] | None = None
            if records:
                r = records[-1]
                last = [r.kind, r.account, r.counterparty, r.amount]
            line = {
                "step": step,
                "op": op,
                "status": status,
                "error": error,
                "value": value,
                "accounts": [[a.id.value, a.balance] for a in accounts],
                "records": len(records),
                "last": last,
            }
            print(json.dumps(line, separators=(",", ":")))


if __name__ == "__main__":
    main()
