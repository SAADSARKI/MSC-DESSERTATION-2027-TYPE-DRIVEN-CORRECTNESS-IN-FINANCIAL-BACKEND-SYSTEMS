use crate::types::account_id::AccountId;
use crate::types::money::Amount;

/// One entry of the transaction history.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionRecord {
    pub kind: &'static str,
    pub account: AccountId,
    pub counterparty: Option<AccountId>,
    pub amount: Amount,
}
