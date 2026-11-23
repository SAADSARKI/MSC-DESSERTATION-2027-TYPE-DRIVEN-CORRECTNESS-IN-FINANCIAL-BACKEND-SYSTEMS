/// One entry of the transaction history.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionRecord {
    pub kind: &'static str,
    pub account: String,
    pub counterparty: String,
    pub amount: u64,
}
