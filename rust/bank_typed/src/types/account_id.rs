use std::cmp::Ordering;

use crate::types::errors::BankError;

/// An account identifier. The field is private and there is no setter, so an
/// identifier is never empty and never changes after it is created.
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
