//! Representation-only diagnostics; readiness remains owned by `RuntimeState`.
use axum::{Json, Router, routing::get};
use serde::Serialize;

#[derive(Clone, Debug, Default, Serialize)]
pub struct NativeBackendDiagnostics {
    pub backend: &'static str,
    pub version: &'static str,
    pub capabilities: &'static [&'static str],
    #[serde(skip_serializing_if = "Option::is_none")]
    pub available: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub authoritative: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub python_fallback: Option<bool>,
}

/// Mount diagnostics without changing health or readiness decisions.
pub fn native_backend_router(diagnostics: NativeBackendDiagnostics) -> Router {
    Router::new().route(
        "/health/native-backend",
        get(move || {
            let diagnostics = diagnostics.clone();
            async move { Json(diagnostics) }
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request};
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    #[tokio::test]
    async fn diagnostics_preserve_optional_wire_fields_and_caller_version() {
        for flags in [
            (None, None, None),
            (Some(true), None, None),
            (None, Some(true), Some(false)),
        ] {
            let diagnostics = NativeBackendDiagnostics {
                backend: "test-rust",
                version: "caller-1.2",
                capabilities: &["verify"],
                available: flags.0,
                authoritative: flags.1,
                python_fallback: flags.2,
            };
            let router = native_backend_router(diagnostics);
            let response = router
                .oneshot(
                    Request::builder()
                        .uri("/health/native-backend")
                        .body(Body::empty())
                        .unwrap(),
                )
                .await
                .unwrap();
            assert_eq!(response.status(), 200);
            let body = response.into_body().collect().await.unwrap().to_bytes();
            let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
            let mut expected = serde_json::json!({"backend":"test-rust", "version":"caller-1.2", "capabilities":["verify"]});
            for (name, flag) in [
                ("available", flags.0),
                ("authoritative", flags.1),
                ("python_fallback", flags.2),
            ] {
                if let Some(flag) = flag {
                    expected[name] = flag.into();
                }
            }
            assert_eq!(value, expected);
        }
    }
}
