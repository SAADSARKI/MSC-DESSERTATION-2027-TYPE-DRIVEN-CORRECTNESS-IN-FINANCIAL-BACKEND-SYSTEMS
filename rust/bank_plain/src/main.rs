#![forbid(unsafe_code)]

use bank_plain::{Account, BankError, FinancialService};

fn parse_amount(field: &str) -> Result<Result<u64, BankError>, String> {
    let raw: i128 = field
        .parse::<i128>()
        .map_err(|e| format!("invalid amount field {field:?}: {e}"))?;
    if raw < 0 { return Ok(Err(BankError::InvalidAmount)); }
    let value = u64::try_from(raw).map_err(|e| format!("amount out of range {field:?}: {e}"))?;
    Ok(Ok(value))
}

fn create(service: &mut FinancialService, account: &str) -> Result<Option<u64>, BankError> {
    service.create_account(account)?;
    Ok(None)
}

fn balance(service: &FinancialService, account: &str) -> Result<Option<u64>, BankError> {
    let value = service.balance(account)?;
    Ok(Some(value))
}

fn deposit(
    service: &mut FinancialService,
    account: &str,
    amount: Result<u64, BankError>,
) -> Result<Option<u64>, BankError> {
    let amount = amount?;
    service.deposit(account, amount)?;
    Ok(None)
}

fn withdraw(
    service: &mut FinancialService,
    account: &str,
    amount: Result<u64, BankError>,
) -> Result<Option<u64>, BankError> {
    let amount = amount?;
    service.withdraw(account, amount)?;
    Ok(None)
}

fn transfer(
    service: &mut FinancialService,
    account: &str,
    to: &str,
    amount: Result<u64, BankError>,
) -> Result<Option<u64>, BankError> {
    let amount = amount?;
    service.transfer(account, to, amount)?;
    Ok(None)
}

fn apply(
    service: &mut FinancialService,
    op: &str,
    account: &str,
    to: &str,
    amount: &str,
) -> Result<Result<Option<u64>, BankError>, String> {
    match op {
        "create" => Ok(create(service, account)),
        "balance" => Ok(balance(service, account)),
        "deposit" => Ok(deposit(service, account, parse_amount(amount)?)),
        "withdraw" => Ok(withdraw(service, account, parse_amount(amount)?)),
        "transfer" => Ok(transfer(service, account, to, parse_amount(amount)?)),
        other => Err(format!("unknown operation {other:?}")),
    }
}

fn format_line(
    step: usize,
    op: &str,
    result: &Result<Option<u64>, BankError>,
    service: &FinancialService,
) -> String {
    let (status, error, value) = match result {
        Ok(Some(v)) => ("ok", String::from("null"), v.to_string()),
        Ok(None) => ("ok", String::from("null"), String::from("null")),
        Err(e) => ("error", format!("\"{}\"", e.code()), String::from("null")),
    };

    let mut accounts: Vec<&Account> = service.accounts().values().collect();
    accounts.sort_by(|a, b| a.id.cmp(&b.id));
    let accounts_json: Vec<String> = accounts
        .iter()
        .map(|a| format!("[\"{}\",{}]", a.id, a.balance))
        .collect();

    let records = service.records();
    let last = match records.last() {
        Some(r) => format!(
            "[\"{}\",\"{}\",\"{}\",{}]",
            r.kind, r.account, r.counterparty, r.amount
        ),
        None => String::from("null"),
    };

    format!(
        "{{\"step\":{},\"op\":\"{}\",\"status\":\"{}\",\"error\":{},\"value\":{},\"accounts\":[{}],\"records\":{},\"last\":{}}}",
        step,
        op,
        status,
        error,
        value,
        accounts_json.join(","),
        records.len(),
        last
    )
}

fn main() -> Result<(), String> {
    let path = std::env::args()
        .nth(1)
        .ok_or_else(|| String::from("usage: bank_plain_runner <ops.csv>"))?;
    let text = std::fs::read_to_string(&path).map_err(|e| format!("cannot read {path}: {e}"))?;

    let mut service = FinancialService::new();
    for (step, line) in text.lines().skip(1).enumerate() {
        let mut fields = line.split(',');
        let op = fields.next().ok_or_else(|| format!("step {step}: missing op field"))?;
        let account = fields.next().ok_or_else(|| format!("step {step}: missing account field"))?;
        let to = fields.next().ok_or_else(|| format!("step {step}: missing to field"))?;
        let amount = fields.next().ok_or_else(|| format!("step {step}: missing amount field"))?;

        let result = apply(&mut service, op, account, to, amount)?;
        println!("{}", format_line(step, op, &result, &service));
    }
    Ok(())
}
