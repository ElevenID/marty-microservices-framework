use std::{collections::BTreeSet, path::Path};

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct Inventory {
    schema_version: u32,
    capabilities: Vec<Capability>,
}

#[derive(Debug, Deserialize)]
struct Capability {
    id: String,
    owner: String,
    status: String,
}

#[test]
fn every_intended_capability_has_one_rust_owner() {
    let inventory: Inventory =
        serde_json::from_str(include_str!("../../../contracts/mmf-capabilities.json"))
            .expect("valid capability inventory");
    assert_eq!(inventory.schema_version, 1);
    assert_eq!(inventory.capabilities.len(), 18);

    let mut ids = BTreeSet::new();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for capability in inventory.capabilities {
        assert!(
            ids.insert(capability.id.clone()),
            "duplicate {}",
            capability.id
        );
        assert!(capability.owner.starts_with("mmf-"), "non-MMF owner");
        assert_eq!(
            capability.status, "native-active",
            "inactive {}",
            capability.id
        );
        assert!(
            root.join("crates")
                .join(&capability.owner)
                .join("Cargo.toml")
                .is_file(),
            "missing canonical owner crate {}",
            capability.owner
        );
    }
}

#[test]
fn retired_python_source_and_packaging_are_absent() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for retired in [
        "mmf",
        "examples",
        "ops",
        "scripts",
        "tools",
        "deploy",
        "platform_plugins",
        "test_reports",
        "pyproject.toml",
        "uv.lock",
        "MANIFEST.in",
        ".python-version",
        ".secrets.baseline",
    ] {
        assert!(
            !root.join(retired).exists(),
            "retired path returned: {retired}"
        );
    }

    assert!(
        root.join(".github/workflows/release.yml").is_file(),
        "Rust release channel is required after Python publication retirement"
    );
    assert!(
        root.join("dependency-health.yml").is_file(),
        "Rust dependency-health policy is required"
    );
}

#[test]
fn release_checksums_match_github_asset_names() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let workflow = std::fs::read_to_string(root.join(".github/workflows/release.yml"))
        .expect("read Rust release workflow");

    assert!(
        workflow.contains("> \"release/${crate}.txt\""),
        "crate manifests must be emitted at the release root"
    );
    assert!(
        !workflow.contains("release/package-manifests"),
        "GitHub flattens release assets, so checksums cannot contain nested manifest paths"
    );
    assert!(
        workflow.contains("find release-assets -mindepth 2 -type f"),
        "the release job must reject nested assets before generating checksums"
    );
}

#[test]
fn required_license_check_runs_for_every_protected_change() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let workflow = std::fs::read_to_string(root.join(".github/workflows/license-compliance.yml"))
        .expect("read Rust license workflow")
        .replace("\r\n", "\n");

    assert!(workflow.contains("pull_request:\n    branches: [main]"));
    assert!(workflow.contains("merge_group:\n    types: [checks_requested]"));
    assert!(
        !workflow.contains("    paths:"),
        "a required check must not be skipped by path filters"
    );
}
