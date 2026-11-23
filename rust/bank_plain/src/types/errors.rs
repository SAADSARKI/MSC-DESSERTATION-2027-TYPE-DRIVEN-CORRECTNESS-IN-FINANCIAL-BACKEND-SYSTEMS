/// One variant per error code of the specification.
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
