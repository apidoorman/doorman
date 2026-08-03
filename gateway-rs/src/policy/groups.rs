use std::collections::HashSet;

use http::StatusCode;
use serde_json::Value;

use super::{PolicyFailure, PolicyStage};
use crate::storage::models::string_list_field;

pub fn enforce_group_access(api: &Value, user: &Value) -> Result<(), PolicyFailure> {
    let user_groups: HashSet<String> = string_list_field(user, "groups").into_iter().collect();
    let allowed_groups = string_list_field(api, "api_allowed_groups");
    if allowed_groups
        .iter()
        .any(|group| user_groups.contains(group))
    {
        Ok(())
    } else {
        Err(PolicyFailure::new(
            PolicyStage::Group,
            StatusCode::UNAUTHORIZED,
            "You do not have the correct group for this",
            "You do not have the correct group for this",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn requires_group_intersection_like_python() {
        let api = json!({ "api_allowed_groups": ["ops"] });
        let user = json!({ "groups": ["admin", "ops"] });
        assert!(enforce_group_access(&api, &user).is_ok());

        let user = json!({ "groups": ["admin"] });
        assert!(enforce_group_access(&api, &user).is_err());
    }
}
