#![forbid(unsafe_code)]

use std::collections::HashMap;

pub const M: u64 = u64::MAX; // [ENF:I1]

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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Account {
    pub id: String,
    pub balance: u64,
}

impl Account {
    pub fn debit(&mut self, amount: u64) -> Result<(), BankError> {
        if self.balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]
        self.balance -= amount;
        Ok(())
    }

    pub fn credit(&mut self, amount: u64) -> Result<(), BankError> {
        if amount > M - self.balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]
        self.balance += amount;
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionRecord {
    pub kind: &'static str,
    pub account: String,
    pub counterparty: String,
    pub amount: u64,
}

#[derive(Debug)]
pub struct FinancialService {
    accounts: HashMap<String, Account>,
    records: Vec<TransactionRecord>,
}

impl FinancialService {
    pub fn new() -> FinancialService {
        FinancialService {
            accounts: HashMap::new(),
            records: Vec::new(),
        }
    }

    pub fn accounts(&self) -> &HashMap<String, Account> {
        &self.accounts
    }

    pub fn records(&self) -> &[TransactionRecord] {
        &self.records
    }

    pub fn create_account(&mut self, id: &str) -> Result<(), BankError> {
        if id.is_empty() { return Err(BankError::InvalidAccountId); } // [ENF:I4]
        if self.accounts.contains_key(id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]
        let account = Account { id: id.to_string(), balance: 0 };
        self.accounts.insert(id.to_string(), account);
        Ok(())
    }

    pub fn balance(&self, id: &str) -> Result<u64, BankError> {
        let account = self.accounts.get(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        Ok(account.balance)
    }

    pub fn deposit(&mut self, id: &str, amount: u64) -> Result<(), BankError> {
        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        let account = self.accounts.get_mut(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        account.credit(amount)?;
        self.records.push(TransactionRecord {
            kind: "deposit",
            account: id.to_string(),
            counterparty: String::new(),
            amount,
        });
        Ok(())
    }

    pub fn withdraw(&mut self, id: &str, amount: u64) -> Result<(), BankError> {
        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        let account = self.accounts.get_mut(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        account.debit(amount)?;
        self.records.push(TransactionRecord {
            kind: "withdraw",
            account: id.to_string(),
            counterparty: String::new(),
            amount,
        });
        Ok(())
    }

    pub fn transfer(&mut self, from: &str, to: &str, amount: u64) -> Result<(), BankError> {
        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        let from_balance = self.accounts.get(from).ok_or(BankError::AccountNotFound)?.balance; // [ENF:I4]
        let to_balance = self.accounts.get(to).ok_or(BankError::AccountNotFound)?.balance; // [ENF:I4]
        if from_balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]
        if amount > M - to_balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]
        let source = self.accounts.get_mut(from).ok_or(BankError::AccountNotFound)?;
        source.balance -= amount; // [ENF:I2]
        let destination = self.accounts.get_mut(to).ok_or(BankError::AccountNotFound)?;
        destination.balance += amount; // [ENF:I2]
        self.records.push(TransactionRecord {
            kind: "transfer",
            account: from.to_string(),
            counterparty: to.to_string(),
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
