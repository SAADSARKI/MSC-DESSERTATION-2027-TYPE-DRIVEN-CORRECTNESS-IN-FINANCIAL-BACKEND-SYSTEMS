use std::collections::HashMap;

use crate::domain::account::Account;
use crate::domain::record::TransactionRecord;
use crate::repository::ledger::Ledger;
use crate::types::account_id::AccountId;
use crate::types::errors::BankError;
use crate::types::money::Amount;

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

    pub fn accounts(&self) -> &HashMap<AccountId, Account> {
        self.ledger.accounts()
    }

    pub fn records(&self) -> &[TransactionRecord] {
        self.ledger.records()
    }

    pub fn create_account(&mut self, id: AccountId) -> Result<(), BankError> {
        if self.ledger.contains(&id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]
        let mut txn = self.ledger.begin();
        txn.save(Account { id, balance: 0 });
        txn.commit();
        Ok(())
    }

    pub fn balance(&self, id: &AccountId) -> Result<u64, BankError> {
        let account = self.ledger.find(id)?;
        Ok(account.balance)
    }

    pub fn deposit(&mut self, id: &AccountId, amount: Amount) -> Result<(), BankError> {
        let mut txn = self.ledger.begin();
        let mut account = txn.load(id)?;
        account.credit(amount)?;
        txn.save(account);
        txn.record(TransactionRecord {
            kind: "deposit",
            account: id.clone(),
            counterparty: None,
            amount,
        });
        txn.commit();
        Ok(())
    }

    pub fn withdraw(&mut self, id: &AccountId, amount: Amount) -> Result<(), BankError> {
        let mut txn = self.ledger.begin();
        let mut account = txn.load(id)?;
        account.debit(amount)?;
        txn.save(account);
        txn.record(TransactionRecord {
            kind: "withdraw",
            account: id.clone(),
            counterparty: None,
            amount,
        });
        txn.commit();
        Ok(())
    }

    pub fn transfer(&mut self, from: &AccountId, to: &AccountId, amount: Amount) -> Result<(), BankError> {
        let mut txn = self.ledger.begin();
        let mut source = txn.load(from)?;
        let mut destination = txn.load(to)?;
        if source.balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]
        let new_to = destination.balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]
        source.balance -= amount.value(); // [ENF:I2]
        destination.balance = new_to; // [ENF:I2]
        txn.save(source);
        txn.save(destination);
        txn.record(TransactionRecord {
            kind: "transfer",
            account: from.clone(),
            counterparty: Some(to.clone()),
            amount,
        });
        txn.commit();
        Ok(())
    }
}
