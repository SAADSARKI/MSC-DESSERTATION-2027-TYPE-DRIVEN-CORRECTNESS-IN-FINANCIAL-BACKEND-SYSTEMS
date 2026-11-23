#![forbid(unsafe_code)]
#![deny(unused_must_use)]

use std::cmp::Ordering;
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BankError {
    InvalidAccountId,
    DuplicateAccount,
    AccountNotFound,
    InvalidAmount,
    InsufficientFunds,
    BalanceLimitExceeded,
}

impl BankError {
    pub fn code(&self) -> &'static str {
        match self {
            BankError::InvalidAccountId => "INVALID_ACCOUNT_ID",
            BankError::DuplicateAccount => "DUPLICATE_ACCOUNT",
            BankError::AccountNotFound => "ACCOUNT_NOT_FOUND",
            BankError::InvalidAmount => "INVALID_AMOUNT",
            BankError::InsufficientFunds => "INSUFFICIENT_FUNDS",
            BankError::BalanceLimitExceeded => "BALANCE_LIMIT_EXCEEDED",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Amount(u64); // [ENF:I3]

impl Amount {
    pub fn new(value: u64) -> Result<Amount, BankError> {
        if value == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        Ok(Amount(value))
    }

    pub fn value(&self) -> u64 {
        self.0
    }
}

#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AccountId(String); // [ENF:I4]

impl AccountId {
    pub fn new(s: &str) -> Result<AccountId, BankError> {
        if s.is_empty() { return Err(BankError::InvalidAccountId); } // [ENF:I4]
        Ok(AccountId(s.to_string()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl Ord for AccountId {
    fn cmp(&self, other: &Self) -> Ordering {
        self.0.cmp(&other.0)
    }
}

impl PartialOrd for AccountId {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Account {
    pub id: AccountId,
    pub balance: u64,
}

impl Account {
    pub fn debit(&mut self, amount: Amount) -> Result<(), BankError> {
        if self.balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]
        self.balance -= amount.value();
        Ok(())
    }

    pub fn credit(&mut self, amount: Amount) -> Result<(), BankError> {
        let new_balance = self.balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]
        self.balance = new_balance;
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionRecord {
    pub kind: &'static str,
    pub account: AccountId,
    pub counterparty: Option<AccountId>,
    pub amount: Amount,
}

#[derive(Debug)]
pub struct FinancialService {
    accounts: HashMap<AccountId, Account>,
    records: Vec<TransactionRecord>,
}

impl FinancialService {
    pub fn new() -> FinancialService {
        FinancialService {
            accounts: HashMap::new(),
            records: Vec::new(),
        }
    }
    pub fn accounts(&self) -> &HashMap<AccountId, Account> {
        &self.accounts
    }

    pub fn records(&self) -> &[TransactionRecord] {
        &self.records
    }

    pub fn create_account(&mut self, id: AccountId) -> Result<(), BankError> {
        if self.accounts.contains_key(&id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]
        let account = Account { id: id.clone(), balance: 0 };
        self.accounts.insert(id, account);
        Ok(())
    }

    pub fn balance(&self, id: &AccountId) -> Result<u64, BankError> {
        let account = self.accounts.get(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        Ok(account.balance)
    }

    pub fn deposit(&mut self, id: &AccountId, amount: Amount) -> Result<(), BankError> {
        let account = self.accounts.get_mut(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        account.credit(amount)?;
        self.records.push(TransactionRecord {
            kind: "deposit",
            account: id.clone(),
            counterparty: None,
            amount,
        });
        Ok(())
    }

    pub fn withdraw(&mut self, id: &AccountId, amount: Amount) -> Result<(), BankError> {
        let account = self.accounts.get_mut(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        account.debit(amount)?;
        self.records.push(TransactionRecord {
            kind: "withdraw",
            account: id.clone(),
            counterparty: None,
            amount,
        });
        Ok(())
    }

    pub fn transfer(&mut self, from: &AccountId, to: &AccountId, amount: Amount) -> Result<(), BankError> {
        let from_balance = self.accounts.get(from).ok_or(BankError::AccountNotFound)?.balance; // [ENF:I4]
        let to_balance = self.accounts.get(to).ok_or(BankError::AccountNotFound)?.balance; // [ENF:I4]
        if from_balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]
        let new_to = to_balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]
        let source = self.accounts.get_mut(from).ok_or(BankError::AccountNotFound)?;
        source.balance -= amount.value(); // [ENF:I2]
        let destination = self.accounts.get_mut(to).ok_or(BankError::AccountNotFound)?;
        destination.balance = new_to; // [ENF:I2]
        self.records.push(TransactionRecord {
            kind: "transfer",
            account: from.clone(),
            counterparty: Some(to.clone()),
            amount,
        });
        Ok(())
    }
}

impl Default for FinancialService {
    fn default() -> Self {
        Self::new()
    }
}
