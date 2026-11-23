//! Rust-Plain financial backend (dissertation prototype, version 2).
//!
//! Same layers and the same unit of work as Rust-Typed, but amounts and
//! balances are plain `u64`, identifiers are plain `String`, and every rule is
//! an explicit check. Default lints only (no `deny(unused_must_use)`).
//!
//! * `types`      the balance limit `M` and `BankError`
//! * `domain`     entities (`Account`, `TransactionRecord`)
//! * `repository` the in-memory ledger and its unit of work (`LedgerTxn`)
//! * `services`   the five operations (`FinancialService`)
#![forbid(unsafe_code)]

pub mod domain;
pub mod repository;
pub mod services;
pub mod types;

pub use domain::account::Account;
pub use domain::record::TransactionRecord;
pub use repository::ledger::{Ledger, LedgerTxn};
pub use services::financial_service::FinancialService;
pub use types::errors::BankError;
pub use types::money::M;
