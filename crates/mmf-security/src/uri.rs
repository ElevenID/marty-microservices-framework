/// Encode one URI component, preserving unreserved ASCII and using UTF-8 escapes.
pub(crate) fn percent_encode_component(value: &str) -> String {
    value
        .bytes()
        .map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                char::from(byte).to_string()
            }
            _ => format!("%{byte:02X}"),
        })
        .collect()
}

pub(crate) fn valid_https_url(value: &str) -> bool {
    !value.contains('#') && authority(value, "https://").is_some_and(valid_authority)
}

pub(crate) fn valid_redirect_uri(value: &str) -> bool {
    !value.contains('#')
        && (valid_https_url(value)
            || authority(value, "http://").is_some_and(|authority| {
                host(authority).is_some_and(|host| {
                    host.eq_ignore_ascii_case("localhost") || host == "127.0.0.1" || host == "[::1]"
                })
            }))
}

pub(crate) fn valid_native_redirect_uri(value: &str) -> bool {
    if value.contains('#') {
        return false;
    }
    if valid_redirect_uri(value) {
        return true;
    }
    let Some((scheme, remainder)) = value.split_once("://") else {
        return false;
    };
    !matches!(
        scheme.to_ascii_lowercase().as_str(),
        "http" | "https" | "javascript" | "data" | "file"
    ) && valid_scheme(scheme)
        && !remainder.is_empty()
        && !remainder.chars().any(char::is_whitespace)
}

fn authority<'a>(value: &'a str, scheme: &str) -> Option<&'a str> {
    let remainder = value.strip_prefix(scheme)?;
    let authority = remainder.split(['/', '?', '#']).next().unwrap_or_default();
    valid_authority(authority).then_some(authority)
}

fn valid_authority(authority: &str) -> bool {
    !authority.is_empty()
        && !authority.contains('@')
        && !authority.chars().any(char::is_whitespace)
        && host(authority).is_some()
}

fn host(authority: &str) -> Option<&str> {
    if authority.starts_with('[') {
        let end = authority.find(']')?;
        let host = &authority[..=end];
        let suffix = &authority[end + 1..];
        return (suffix.is_empty()
            || suffix.strip_prefix(':').is_some_and(|port| {
                !port.is_empty() && port.bytes().all(|byte| byte.is_ascii_digit())
            }))
        .then_some(host);
    }
    let (host, port) = authority
        .split_once(':')
        .map_or((authority, None), |(host, port)| (host, Some(port)));
    (!host.is_empty()
        && !host.starts_with('.')
        && !host.ends_with('.')
        && host
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'-'))
        && port
            .is_none_or(|port| !port.is_empty() && port.bytes().all(|byte| byte.is_ascii_digit())))
    .then_some(host)
}

fn valid_scheme(scheme: &str) -> bool {
    let mut bytes = scheme.bytes();
    bytes.next().is_some_and(|byte| byte.is_ascii_alphabetic())
        && bytes.all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'+' | b'-' | b'.'))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn component_encoding_preserves_bytes_and_uri_delimiter_boundaries() {
        for (input, expected) in [
            ("", ""),
            ("AZaz09-_.~", "AZaz09-_.~"),
            (" +%", "%20%2B%25"),
            (
                ":/?#[]@!$&'()*+,;=",
                "%3A%2F%3F%23%5B%5D%40%21%24%26%27%28%29%2A%2B%2C%3B%3D",
            ),
            ("\0\t\r\n\u{7f}", "%00%09%0D%0A%7F"),
            ("café/雪", "caf%C3%A9%2F%E9%9B%AA"),
            ("%2F", "%252F"),
        ] {
            assert_eq!(percent_encode_component(input), expected, "{input:?}");
        }
    }

    #[test]
    fn redirects_require_exact_secure_or_loopback_authorities() {
        assert!(valid_redirect_uri("https://client.example/callback"));
        assert!(valid_redirect_uri("http://localhost:8080/callback"));
        assert!(valid_redirect_uri("http://[::1]:8080/callback"));
        assert!(!valid_redirect_uri(
            "http://localhost.attacker.example/callback"
        ));
        assert!(!valid_redirect_uri("https:///callback"));
        assert!(!valid_redirect_uri("https://user@client.example/callback"));
        assert!(!valid_redirect_uri(
            "https://client.example/callback#fragment"
        ));
        assert!(valid_native_redirect_uri("com.example.app://callback"));
        assert!(!valid_native_redirect_uri("javascript://alert"));
    }
}
