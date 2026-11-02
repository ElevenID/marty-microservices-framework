//! Dependency-light secret comparison shared by security contracts and consumers.

#[must_use]
pub fn constant_time_secret_eq(expected: &[u8], candidate: &[u8]) -> bool {
    let mut difference = expected.len() ^ candidate.len();
    let maximum = expected.len().max(candidate.len());
    for index in 0..maximum {
        difference |= usize::from(
            expected.get(index).copied().unwrap_or_default()
                ^ candidate.get(index).copied().unwrap_or_default(),
        );
    }
    difference == 0
}

#[cfg(test)]
mod tests {
    use super::constant_time_secret_eq;

    #[test]
    fn secret_comparison_covers_binary_boundaries_and_mismatch_positions() {
        let bytes: Vec<u8> = (0..=u8::MAX).collect();
        assert!(constant_time_secret_eq(&bytes, &bytes));
        for index in [0, bytes.len() / 2, bytes.len() - 1] {
            let mut different = bytes.clone();
            different[index] ^= 1;
            assert!(!constant_time_secret_eq(&bytes, &different));
            assert!(!constant_time_secret_eq(&different, &bytes));
        }
        for (left, right) in [
            (&b""[..], &b"\0"[..]),
            (&b"same"[..], &b"same\0"[..]),
            (&b"\xff\0"[..], &b"\xff"[..]),
        ] {
            assert!(!constant_time_secret_eq(left, right));
            assert!(!constant_time_secret_eq(right, left));
        }
    }

    #[test]
    fn equal_and_unequal_secrets_match_existing_behavior() {
        assert!(constant_time_secret_eq(b"same", b"same"));
        assert!(!constant_time_secret_eq(b"same", b"different"));
        assert!(!constant_time_secret_eq(b"same", b"samf"));
        assert!(constant_time_secret_eq(b"", b""));
        assert!(!constant_time_secret_eq(b"", b"nonempty"));
        assert!(!constant_time_secret_eq(b"\0", b"\0\0"));
    }
}
