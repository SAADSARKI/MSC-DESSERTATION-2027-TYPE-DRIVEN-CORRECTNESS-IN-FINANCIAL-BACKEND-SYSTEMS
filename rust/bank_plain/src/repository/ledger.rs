use std::collections::HashMap;

use crate::domain::account::Account;
use crate::domain::record::TransactionRecord;
use crate::types::errors::BankError;

/// The in-memory store of accounts and transaction records.
///
/// Reads are open to everyone. Writes (`put`, `append`) are crate-private and
/// are made by `LedgerTxn::commit`.
#[derive(Debug, Default)]
pub struct Ledger {
    accounts: HashMap<String, Account>,
    records: Vec<TransactionRecord>,
}

impl Ledger {
    pub fn new() -> Ledger {
        Ledger {
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

    pub fn contains(&self, id: &str) -> bool {
        self.accounts.contains_key(id)
    }

    pub fn find(&self, id: &str) -> Result<&Account, BankError> {
        let account = self.accounts.get(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]
        Ok(account)
    }

    /// Opens a unit of work. The transaction holds the only mutable borrow of
    /// the ledger until it is committed or dropped.
    pub fn begin(&mut self) -> LedgerTxn<'_> {
        LedgerTxn {
            ledger: self,
            accounts: Vec::new(),
            records: Vec::new(),
        }
    }

    pub(crate) fn put(&mut self, account: Account) {
        self.accounts.insert(account.id.clone(), account);
    }

    pub(crate) fn append(&mut self, record: TransactionRecord) {
        self.records.push(record);
    }
}

/// A unit of work on the ledger, in the role of a database transaction.
///
/// `load` returns a copy of an account; `save` and `record` stage changes;
/// `commit` applies all staged changes together and consumes the transaction.
/// A transaction that is dropped without `commit` (for example on an early
/// return through `?`) changes nothing.
#[must_use = "a transaction changes nothing unless it is committed"]
#[derive(Debug)]
pub struct LedgerTxn<'a> { // [ENF:I5]
    ledger: &'a mut Ledger,
    accounts: Vec<Account>,
    records: Vec<TransactionRecord>,
}

impl LedgerTxn<'_> {
    pub fn load(&self, id: &str) -> Result<Account, BankError> {
        let account = self.ledger.find(id)?;
        Ok(account.clone())
    }

    pub fn save(&mut self, account: Account) {
        self.accounts.push(account);
    }

    pub fn record(&mut self, record: TransactionRecord) {
        self.records.push(record);
    }

    pub fn commit(self) { // [ENF:I5]
        for account in self.accounts {
            self.ledger.put(account);
        }
        for record in self.records {
            self.ledger.append(record);
        }
    }
}
