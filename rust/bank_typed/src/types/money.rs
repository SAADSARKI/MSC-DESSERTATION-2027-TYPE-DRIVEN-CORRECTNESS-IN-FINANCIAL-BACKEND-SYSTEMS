use crate::types::errors::BankError;

/// A transaction amount in kobo. The field is private, so the only way to
/// obtain an `Amount` is `Amount::new`, and a zero amount cannot exist.
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
