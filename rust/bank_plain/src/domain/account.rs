use crate::types::errors::BankError;
use crate::types::money::M;

/// An account. There is no default balance: every construction names it.
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
