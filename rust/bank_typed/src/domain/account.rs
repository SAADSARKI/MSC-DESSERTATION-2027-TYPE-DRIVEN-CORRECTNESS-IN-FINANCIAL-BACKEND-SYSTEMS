use crate::types::account_id::AccountId;
use crate::types::errors::BankError;
use crate::types::money::Amount;

/// An account. There is no default balance: every construction names it.
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
