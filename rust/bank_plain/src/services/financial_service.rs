use std::collections::HashMap;

use crate::domain::account::Account;
use crate::domain::record::TransactionRecord;
use crate::repository::ledger::Ledger;
use crate::types::errors::BankError;
use crate::types::money::M;

/// The five operations of the backend. Each state-changing operation opens
/// one `LedgerTxn`, performs all of its checks, stages its changes and
/// commits. Any `?` before `commit` drops the transaction, so nothing changes.
#[derive(Debug, Default)]
pub struct FinancialService {
    ledger: Ledger,
}

impl FinancialService {
    pub fn new() -> FinancialService {
        FinancialService { ledger: Ledger::new() }
    }

    pub fn accounts(&self) -> &HashMap<String, Account> {
        self.ledger.accounts()
    }

    pub fn records(&self) -> &[TransactionRecord] {
        self.ledger.records()
    }

    pub fn create_account(&mut self, id: &str) -> Result<(), BankError> {
        if id.is_empty() { return Err(BankError::InvalidAccountId); } // [ENF:I4]
        if self.ledger.contains(id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]
        let mut txn = self.ledger.begin();
        txn.save(Account { id: id.to_string(), balance: 0 });
        txn.commit();
        Ok(())
    }

    pub fn balance(&self, id: &str) -> Result<u64, BankError> {
        let account = self.ledger.find(id)?;
        Ok(account.balance)
    }

    pub fn deposit(&mut self, id: &str, amount: u64) -> Result<(), BankError> {
        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        let mut txn = self.ledger.begin();
        let mut account = txn.load(id)?;
        account.credit(amount)?;
        txn.save(account);
        txn.record(TransactionRecord {
            kind: "deposit",
            account: id.to_string(),
            counterparty: String::new(),
            amount,
        });
        txn.commit();
        Ok(())
    }

    pub fn withdraw(&mut self, id: &str, amount: u64) -> Result<(), BankError> {
        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        let mut txn = self.ledger.begin();
        let mut account = txn.load(id)?;
        account.debit(amount)?;
        txn.save(account);
        txn.record(TransactionRecord {
            kind: "withdraw",
            account: id.to_string(),
            counterparty: String::new(),
            amount,
        });
        txn.commit();
        Ok(())
    }

    pub fn transfer(&mut self, from: &str, to: &str, amount: u64) -> Result<(), BankError> {
        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]
        let mut txn = self.ledger.begin();
        let mut source = txn.load(from)?;
        let mut destination = txn.load(to)?;
        if source.balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]
        if amount > M - destination.balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]
        source.balance -= amount; // [ENF:I2]
        destination.balance += amount; // [ENF:I2]
        txn.save(source);
        txn.save(destination);
        txn.record(TransactionRecord {
            kind: "transfer",
            account: from.to_string(),
            counterparty: to.to_string(),
            amount,
        });
        txn.commit();
        Ok(())
    }
}
