//! PII Masking for sensitive fields
//!
//! Pure functions for redacting sensitive data from JSON strings.
//! Follows Let It Crash: no error handling, just best-effort masking.

use regex::Regex;

/// Mask sensitive PII fields in JSON string
///
/// Pure function: Same input always produces same output
/// Follows KISS: Simple regex replacement, no JSON parsing
///
/// Masks these patterns:
/// - `"api_key": "..."` -> `"api_key": "[REDACTED]"`
/// - `"auth_token": "..."` -> `"auth_token": "[REDACTED]"`
/// - `"password": "..."` -> `"password": "[REDACTED]"`
/// - `"access_token": "..."` -> `"access_token": "[REDACTED]"`
/// - `"Authorization": "..."` -> `"Authorization": "[REDACTED]"`
pub fn mask_pii(json: &str) -> String {
    let patterns = vec![
        (r#""api_key"\s*:\s*"[^"]*""#, r#""api_key": "[REDACTED]""#),
        (r#""auth_token"\s*:\s*"[^"]*""#, r#""auth_token": "[REDACTED]""#),
        (r#""password"\s*:\s*"[^"]*""#, r#""password": "[REDACTED]""#),
        (r#""access_token"\s*:\s*"[^"]*""#, r#""access_token": "[REDACTED]""#),
        (r#""Authorization"\s*:\s*"[^"]*""#, r#""Authorization": "[REDACTED]""#),
        (r#""bearer"\s*:\s*"[^"]*""#, r#""bearer": "[REDACTED]""#),
        (r#""Bearer\s+[^"]*""#, r#""Bearer [REDACTED]""#),
    ];

    let mut result = json.to_string();
    for (pattern, replacement) in patterns {
        let re = Regex::new(pattern).expect("Invalid regex pattern");
        result = re.replace_all(&result, replacement).to_string();
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mask_api_key() {
        let input = r#"{"api_key": "secret123", "data": "public"}"#;
        let output = mask_pii(input);
        assert!(output.contains(r#""api_key": "[REDACTED]""#));
        assert!(output.contains(r#""data": "public""#));
    }

    #[test]
    fn test_mask_multiple_fields() {
        let input = r#"{"api_key": "key1", "password": "pass1", "username": "user1"}"#;
        let output = mask_pii(input);
        assert!(output.contains(r#""api_key": "[REDACTED]""#));
        assert!(output.contains(r#""password": "[REDACTED]""#));
        assert!(output.contains(r#""username": "user1""#));
    }

    #[test]
    fn test_mask_bearer_token() {
        let input = r#"{"Authorization": "Bearer sk-abc123xyz"}"#;
        let output = mask_pii(input);
        assert!(output.contains(r#""Authorization": "[REDACTED]""#));
    }

    #[test]
    fn test_no_pii_unchanged() {
        let input = r#"{"workflow_type": "full-workflow", "status": "running"}"#;
        let output = mask_pii(input);
        assert_eq!(input, output);
    }
}
