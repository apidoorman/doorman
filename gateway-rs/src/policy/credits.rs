use http::StatusCode;
use serde_json::Value;

use super::{PolicyFailure, PolicyStage};
use crate::storage::models::{bool_field_default, object_field, string_field, u64_field};

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct CreditDecision {
    pub required: bool,
    pub header_name: Option<String>,
    pub header_value: Option<String>,
    pub user_header_value: Option<String>,
}

pub fn evaluate_credits(
    api: &Value,
    username: Option<&str>,
    credit_defs: &[Value],
    user_credits: &[Value],
) -> Result<CreditDecision, PolicyFailure> {
    let enabled = bool_field_default(api, "api_credits_enabled", false);
    let public = bool_field_default(api, "api_public", false);
    if !enabled || public {
        return Ok(CreditDecision::default());
    }

    let Some(username) = username else {
        return Ok(CreditDecision {
            required: true,
            ..Default::default()
        });
    };
    let group = string_field(api, "api_credit_group").unwrap_or_default();
    if group.is_empty() {
        return Ok(CreditDecision {
            required: true,
            ..Default::default()
        });
    }
    let user_credit = user_credits
        .iter()
        .find(|doc| string_field(doc, "username") == Some(username));
    let available = user_credit
        .and_then(|doc| object_field(doc, "users_credits"))
        .and_then(|credits| credits.get(group))
        .and_then(|credit| u64_field(credit, "available_credits"))
        .unwrap_or(0);
    if available == 0 {
        return Err(PolicyFailure::new(
            PolicyStage::Credits,
            StatusCode::UNAUTHORIZED,
            "GTW008",
            "User does not have any credits",
        ));
    }

    let credit_def = credit_defs
        .iter()
        .find(|doc| string_field(doc, "api_credit_group") == Some(group));
    let header_name = credit_def
        .and_then(|doc| string_field(doc, "api_key_header"))
        .map(str::to_owned);
    let header_value = credit_def
        .and_then(|doc| string_field(doc, "api_key_new").or_else(|| string_field(doc, "api_key")))
        .map(str::to_owned);
    let user_header_value = user_credit
        .and_then(|doc| object_field(doc, "users_credits"))
        .and_then(|credits| credits.get(group))
        .and_then(|credit| string_field(credit, "user_api_key"))
        .map(str::to_owned);

    Ok(CreditDecision {
        required: true,
        header_name,
        header_value,
        user_header_value,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn rejects_credit_enabled_api_without_available_credits() {
        let api = json!({
            "api_credits_enabled": true,
            "api_credit_group": "ai",
        });
        let user_credits = vec![json!({
            "username": "alice",
            "users_credits": { "ai": { "available_credits": 0 } },
        })];
        assert_eq!(
            evaluate_credits(&api, Some("alice"), &[], &user_credits)
                .unwrap_err()
                .error_code,
            "GTW008"
        );
    }

    #[test]
    fn reports_credit_headers_without_deducting() {
        let api = json!({
            "api_credits_enabled": true,
            "api_credit_group": "ai",
        });
        let credit_defs = vec![json!({
            "api_credit_group": "ai",
            "api_key_header": "X-API-Key",
            "api_key": "system-key",
        })];
        let user_credits = vec![json!({
            "username": "alice",
            "users_credits": { "ai": { "available_credits": 2, "user_api_key": "user-key" } },
        })];
        let decision = evaluate_credits(&api, Some("alice"), &credit_defs, &user_credits).unwrap();
        assert!(decision.required);
        assert_eq!(decision.header_name, Some("X-API-Key".to_owned()));
        assert_eq!(decision.header_value, Some("system-key".to_owned()));
        assert_eq!(decision.user_header_value, Some("user-key".to_owned()));
    }
}
