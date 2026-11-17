//! Parser-level replay, not the service's full configuration or SQL cutover gate.
#![allow(clippy::float_cmp)] // Frozen finite parser/clamp results must match exactly.

use std::collections::BTreeMap;

use mmf_config::numeric_config::{
    InvalidConfigNumber, PYTHON_CONFIG_INTEGER_DIGIT_LIMIT, PythonConfigInteger,
    parse_bounded_python_config_float, parse_python_config_float,
};
use serde_json::Value;

fn unicode_oracle() -> Value {
    serde_json::from_str(include_str!(
        "../../../contracts/python-numeric-unicode-oracle.json"
    ))
    .expect("Unicode oracle")
}

#[test]
fn all_64_published_lexical_vectors_match_without_skipping_errors() {
    let fixture: Value = serde_json::from_str(include_str!(
        "../../../contracts/python-config-lexical-observations.json"
    ))
    .expect("frozen configuration parser observations");
    assert_eq!(
        fixture["legacy_observation"]["observed_source"],
        "85b128a85426b3f5aeaf6f948ba5dfa2836e95d8"
    );
    assert_eq!(
        fixture["legacy_observation"]["observed_python_version"],
        "3.12.13"
    );
    let cases = fixture["cases"].as_array().expect("cases");
    assert_eq!(cases.len(), 64);
    for case in cases {
        let kind = case["kind"].as_str().expect("numeric input kind");
        let input = case["input"]
            .as_str()
            .expect("original configuration string");
        let invalid = case.get("expected_error").is_some();
        match kind {
            "integer" => {
                let actual = input.parse::<PythonConfigInteger>();
                if invalid {
                    assert_eq!(actual, Err(InvalidConfigNumber), "{}", case["name"]);
                } else {
                    let bounded = actual.expect("accepted integer").max(1_u64.into());
                    assert_eq!(
                        bounded.as_decimal(),
                        case["expected"]["schedule_limit"].as_str().unwrap(),
                        "{}",
                        case["name"]
                    );
                }
            }
            "float" => {
                let actual = parse_python_config_float(input);
                if invalid {
                    assert!(actual.is_err(), "{}", case["name"]);
                } else {
                    actual.expect("accepted float");
                    let bounded = parse_bounded_python_config_float(input, 0.1, 60.0).unwrap();
                    assert_eq!(
                        bounded,
                        case["expected"]["poll_seconds"].as_f64().unwrap(),
                        "{}",
                        case["name"]
                    );
                }
            }
            unexpected => panic!("unconsumed numeric oracle field: {unexpected}"),
        }
    }
}

#[test]
fn decimal_normalization_matches_the_entire_observed_unicode_surface() {
    let fixture = unicode_oracle();
    assert_eq!(fixture["python_version"], "3.12.13");
    assert_eq!(fixture["unicode_version"], "15.0.0");
    let mut expected = BTreeMap::new();
    for zero in fixture["decimal_zero_codepoints"].as_array().unwrap() {
        let start = u32::try_from(zero.as_u64().unwrap()).unwrap();
        for digit in 0..10 {
            assert!(expected.insert(start + digit, u64::from(digit)).is_none());
        }
    }
    assert_eq!(expected.len(), 680);
    for codepoint in 0..=0x10_FFFF {
        let Some(character) = char::from_u32(codepoint) else {
            continue;
        };
        let input = character.to_string();
        let actual = input
            .parse::<PythonConfigInteger>()
            .ok()
            .and_then(|value| value.to_u64());
        assert_eq!(
            actual,
            expected.get(&codepoint).copied(),
            "U+{codepoint:04X}"
        );
        let floating = parse_python_config_float(&input).ok();
        let expected_float = expected
            .get(&codepoint)
            .map(|digit| f64::from(u32::try_from(*digit).unwrap()));
        assert_eq!(floating, expected_float, "float U+{codepoint:04X}");
    }
}

#[test]
fn numeric_whitespace_matches_observed_runtime_not_broad_python_isspace() {
    let fixture = unicode_oracle();
    for codepoint in fixture["numeric_whitespace_codepoints"].as_array().unwrap() {
        let character =
            char::from_u32(u32::try_from(codepoint.as_u64().unwrap()).unwrap()).unwrap();
        assert_eq!(
            format!("{character}12{character}")
                .parse::<PythonConfigInteger>()
                .unwrap()
                .to_u64(),
            Some(12)
        );
        assert_eq!(
            parse_python_config_float(&format!("{character}1.2{character}")),
            Ok(1.2)
        );
        assert!(
            format!("1{character}2")
                .parse::<PythonConfigInteger>()
                .is_err()
        );
        assert!(parse_python_config_float(&format!("1{character}2")).is_err());
    }
    for codepoint in fixture["rejected_python_whitespace_codepoints"]
        .as_array()
        .unwrap()
    {
        let character =
            char::from_u32(u32::try_from(codepoint.as_u64().unwrap()).unwrap()).unwrap();
        assert!(
            format!("{character}12{character}")
                .parse::<PythonConfigInteger>()
                .is_err()
        );
        assert!(parse_python_config_float(&format!("{character}1.2{character}")).is_err());
    }
}

#[test]
fn integer_digit_policy_counts_leading_zeros_but_not_valid_separators_or_sign() {
    let fixture = unicode_oracle();
    assert_eq!(PYTHON_CONFIG_INTEGER_DIGIT_LIMIT, 4300);
    for case in fixture["integer_edges"].as_array().unwrap() {
        let actual = case["input"]
            .as_str()
            .unwrap()
            .parse::<PythonConfigInteger>();
        if case.get("expected_error").is_some() {
            assert_eq!(actual, Err(InvalidConfigNumber), "{}", case["name"]);
        } else {
            assert_eq!(
                actual.unwrap().as_decimal(),
                case["expected"].as_str().unwrap(),
                "{}",
                case["name"]
            );
        }
    }
}

#[test]
fn ordering_bounds_and_machine_conversions_preserve_exact_values() {
    let values = [
        "-999999999999999999999999",
        "-9223372036854775809",
        "-9223372036854775808",
        "-100",
        "-10",
        "-1",
        "0",
        "1",
        "9",
        "10",
        "30",
        "500",
        "9223372036854775807",
        "9223372036854775808",
        "18446744073709551615",
        "18446744073709551616",
        "1000000000000000000000000000000",
    ]
    .map(|value| value.parse::<PythonConfigInteger>().unwrap());
    for (left_index, left) in values.iter().enumerate() {
        for (right_index, right) in values.iter().enumerate() {
            assert_eq!(left.cmp(right), left_index.cmp(&right_index));
        }
    }
    assert_eq!(values[1].to_i64(), None);
    assert_eq!(values[2].to_i64(), Some(i64::MIN));
    assert_eq!(values[12].to_i64(), Some(i64::MAX));
    assert_eq!(values[13].to_i64(), None);
    assert_eq!(values[14].to_u64(), Some(u64::MAX));
    assert_eq!(values[15].to_u64(), None);
    assert_eq!(PythonConfigInteger::from(-1_i64).to_usize(), None);
    let huge: PythonConfigInteger = "9".repeat(4300).parse().unwrap();
    assert_eq!(huge.to_i64(), None);
    assert_eq!(huge.to_usize(), None);
    assert_eq!(huge.clone().min(500_u64.into()).to_u64(), Some(500));
    assert_eq!(huge.as_decimal(), "9".repeat(4300));
    assert_eq!(values[0].clone().max(30_u64.into()).to_i64(), Some(30));
    assert_eq!("-000".parse::<PythonConfigInteger>().unwrap(), 0_i64.into());
}

#[test]
fn numeric_errors_do_not_retain_or_echo_input_values() {
    let secret = "private-configuration-value-must-not-be-logged";
    for error in [
        secret.parse::<PythonConfigInteger>().unwrap_err(),
        parse_python_config_float(secret).unwrap_err(),
    ] {
        assert_eq!(error.to_string(), "invalid numeric configuration");
        assert!(!format!("{error:?}").contains(secret));
    }
}

#[test]
fn bounded_floats_preserve_ordered_nonfinite_and_signed_zero_behavior() {
    let fixture = unicode_oracle();
    let cases = fixture["float_bound_edges"].as_array().unwrap();
    assert_eq!(cases.len(), 9);
    for case in cases {
        let actual = parse_bounded_python_config_float(
            case["input"].as_str().unwrap(),
            case["minimum"].as_f64().unwrap(),
            case["maximum"].as_f64().unwrap(),
        )
        .unwrap();
        assert_eq!(
            format!("{:016x}", actual.to_bits()),
            case["expected_f64_bits"].as_str().unwrap()
        );
    }
    for (minimum, maximum) in [
        (2.0, 1.0),
        (f64::NAN, 1.0),
        (0.0, f64::NAN),
        (0.0, f64::INFINITY),
        (f64::NEG_INFINITY, 0.0),
    ] {
        assert_eq!(
            parse_bounded_python_config_float("1", minimum, maximum),
            Err(InvalidConfigNumber)
        );
    }
}
