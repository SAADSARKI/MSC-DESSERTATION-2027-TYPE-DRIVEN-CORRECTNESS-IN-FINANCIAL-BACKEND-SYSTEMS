//! Rust-Typed financial backend (dissertation prototype, version 2).
//!
//! The crate is layered in the style of an industrial Rust payments backend:
//!
//! * `types`      value types that carry rules (`Amount`, `AccountId`, `BankError`)
//! * `domain`     entities (`Account`, `TransactionRecord`)
//! * `repository` the in-memory ledger and its unit of work (`LedgerTxn`)
//! * `services`   the five operations (`FinancialService`)
//!
//! State is held in memory only. Every state change goes through a `LedgerTxn`,
//! which plays the role of a database transaction: changes are staged and are
//! applied together by `commit`, or discarded when the transaction is dropped.
#![forbid(unsafe_code)]
#![deny(unused_must_use)]

pub mod domain;
pub mod repository;
pub mod services;
pub mod types;

pub use domain::account::Account;
pub use domain::record::TransactionRecord;
pub use repository::ledger::{Ledger, LedgerTxn};
pub use services::financial_service::FinancialService;
pub use types::account_id::AccountId;
pub use types::errors::BankError;
pub use types::money::Amount;
