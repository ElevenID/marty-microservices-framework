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
    fn equal_and_unequal_secrets_match_existing_behavior() {
        assert!(constant_time_secret_eq(b"same", b"same"));
        assert!(!constant_time_secret_eq(b"same", b"different"));
        assert!(!constant_time_secret_eq(b"same", b"samf"));
        assert!(!constant_time_secret_eq(b"", b"nonempty"));
    }
}
