//! Ergonomic facade for the canonical MMF Rust crates.

#![forbid(unsafe_code)]

pub use mmf_cli as cli;
pub use mmf_config as config;
pub use mmf_core as core;
pub use mmf_data as data;
pub use mmf_messaging as messaging;
pub use mmf_ml as ml;
pub use mmf_observability as observability;
pub use mmf_patterns as patterns;
pub use mmf_platform as platform;
pub use mmf_plugins as plugins;
pub use mmf_push as push;
pub use mmf_resilience as resilience;
pub use mmf_runtime as runtime;
pub use mmf_security as security;
pub use mmf_services as services;
pub use mmf_testkit as testkit;
pub use mmf_workflow as workflow;

#[cfg(test)]
mod tests {
    use super::{core, platform, security};

    #[test]
    fn mesh_contract_reexports_preserve_type_identity() {
        let _: fn(platform::ServiceMeshPolicy) -> security::ServiceMeshPolicy = |policy| policy;
        let _: fn(&dyn platform::ServiceMeshManager) -> &dyn security::ServiceMeshManager =
            |manager| manager;
        let _: fn(security::SecurityError) -> core::MmfError = Into::into;
    }
}
