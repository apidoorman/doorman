use std::{collections::HashMap, fmt, sync::Arc};

use regex::Regex;
use serde_json::Value;

pub type CustomValidator = dyn Fn(&Value, &Value) -> Result<(), String> + Send + Sync + 'static;

#[derive(Clone, Default)]
pub struct ValidatorRegistry {
    validators: HashMap<String, Arc<CustomValidator>>,
}

impl fmt::Debug for ValidatorRegistry {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ValidatorRegistry")
            .field("names", &self.validators.keys().collect::<Vec<_>>())
            .finish()
    }
}

impl ValidatorRegistry {
    pub fn register(
        &mut self,
        name: impl Into<String>,
        validator: impl Fn(&Value, &Value) -> Result<(), String> + Send + Sync + 'static,
    ) {
        self.validators.insert(name.into(), Arc::new(validator));
    }

    fn validate(&self, name: &str, value: &Value, rules: &Value) -> Result<(), String> {
        match self.validators.get(name) {
            Some(validator) => validator(value, rules),
            None => Ok(()),
        }
    }
}

pub fn validate_json(value: &Value, schema: &Value) -> Result<(), String> {
    validate_json_with_registry(value, schema, &ValidatorRegistry::default())
}

pub fn validate_json_with_registry(
    value: &Value,
    schema: &Value,
    registry: &ValidatorRegistry,
) -> Result<(), String> {
    let mapping = schema
        .get("validation_schema")
        .unwrap_or(schema)
        .as_object()
        .ok_or_else(|| "Invalid endpoint validation schema".to_owned())?;
    for (path, rules) in mapping {
        let found = nested_value(value, path);
        validate_value(found, rules, path, registry)?;
    }
    Ok(())
}

fn validate_value(
    value: Option<&Value>,
    rules: &Value,
    path: &str,
    registry: &ValidatorRegistry,
) -> Result<(), String> {
    let required = rules
        .get("required")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let Some(value) = value.filter(|value| !value.is_null()) else {
        return if required {
            Err(format!("Required field {path} is missing"))
        } else {
            Ok(())
        };
    };
    let expected = rules
        .get("type")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let valid_type = match expected {
        "string" => value.is_string(),
        "number" => value.is_number(),
        "boolean" => value.is_boolean(),
        "array" => value.is_array(),
        "object" => value.is_object(),
        _ => true,
    };
    if !valid_type {
        return Err(format!("Expected {expected} at {path}"));
    }
    if let Some(text) = value.as_str() {
        let length = text.chars().count() as f64;
        enforce_range(length, rules, path, "String length")?;
        if let Some(pattern) = rules.get("pattern").and_then(Value::as_str) {
            let regex = Regex::new(pattern)
                .map_err(|_| format!("Invalid validation pattern for {path}"))?;
            if !regex.is_match(text) {
                return Err(format!("String does not match pattern {pattern} at {path}"));
            }
        }
        if let Some(format) = rules.get("format").and_then(Value::as_str) {
            validate_format(text, format, path)?;
        }
    }
    if let Some(number) = value.as_f64() {
        enforce_range(number, rules, path, "Value")?;
    }
    if let Some(items) = value.as_array() {
        enforce_range(items.len() as f64, rules, path, "Array length")?;
        if let Some(item_rules) = rules.get("array_items") {
            for (index, item) in items.iter().enumerate() {
                validate_value(
                    Some(item),
                    item_rules,
                    &format!("{path}[{index}]"),
                    registry,
                )?;
            }
        }
    }
    if let (Some(object), Some(nested)) = (
        value.as_object(),
        rules.get("nested_schema").and_then(Value::as_object),
    ) {
        for (field, nested_rules) in nested {
            validate_value(
                object.get(field),
                nested_rules,
                &format!("{path}.{field}"),
                registry,
            )?;
        }
    }
    if let Some(allowed) = rules.get("enum").and_then(Value::as_array) {
        if !allowed.contains(value) {
            return Err(format!("Value at {path} must be one of {allowed:?}"));
        }
    }
    if let Some(name) = rules.get("custom_validator").and_then(Value::as_str) {
        registry
            .validate(name, value, rules)
            .map_err(|message| format!("{message} at {path}"))?;
    }
    Ok(())
}

fn enforce_range(value: f64, rules: &Value, path: &str, description: &str) -> Result<(), String> {
    if rules
        .get("min")
        .and_then(Value::as_f64)
        .is_some_and(|minimum| value < minimum)
    {
        return Err(format!("{description} is below minimum at {path}"));
    }
    if rules
        .get("max")
        .and_then(Value::as_f64)
        .is_some_and(|maximum| value > maximum)
    {
        return Err(format!("{description} exceeds maximum at {path}"));
    }
    Ok(())
}

fn validate_format(value: &str, format: &str, path: &str) -> Result<(), String> {
    let valid = match format {
        "email" => value
            .split_once('@')
            .is_some_and(|(local, domain)| !local.is_empty() && domain.contains('.')),
        "url" => {
            (value.starts_with("http://") || value.starts_with("https://"))
                && value
                    .split_once("://")
                    .is_some_and(|(_, host)| host.contains('.'))
        }
        "date" => valid_date(value),
        "datetime" => value.contains('T') && value.len() >= 16,
        "uuid" => uuid::Uuid::parse_str(value).is_ok(),
        _ => true,
    };
    if valid {
        Ok(())
    } else {
        Err(format!("Invalid {format} format at {path}"))
    }
}

fn valid_date(value: &str) -> bool {
    let mut parts = value.split('-');
    matches!(
        (
            parts.next().and_then(|part| part.parse::<u16>().ok()),
            parts.next().and_then(|part| part.parse::<u8>().ok()),
            parts.next().and_then(|part| part.parse::<u8>().ok()),
            parts.next(),
        ),
        (Some(year), Some(1..=12), Some(1..=31), None) if year > 0
    )
}

fn nested_value<'a>(root: &'a Value, path: &str) -> Option<&'a Value> {
    let mut current = root;
    for segment in path.split('.') {
        let (field, index) = parse_segment(segment)?;
        if !field.is_empty() {
            current = current.get(field)?;
        }
        if let Some(index) = index {
            current = current.as_array()?.get(index)?;
        }
    }
    Some(current)
}

fn parse_segment(segment: &str) -> Option<(&str, Option<usize>)> {
    if let Some((field, raw_index)) = segment.split_once('[') {
        let index = raw_index.strip_suffix(']')?.parse().ok()?;
        Some((field, Some(index)))
    } else if segment.is_empty() {
        None
    } else {
        Some((segment, None))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn validates_nested_required_types_ranges_and_formats() {
        let schema = json!({
            "validation_schema": {
                "user.email": {"required": true, "type": "string", "format": "email"},
                "scores[0]": {"required": true, "type": "number", "min": 1}
            }
        });
        assert!(
            validate_json(
                &json!({"user": {"email": "a@b.com"}, "scores": [2]}),
                &schema
            )
            .is_ok()
        );
        assert!(validate_json(&json!({"user": {"email": "bad"}, "scores": [0]}), &schema).is_err());
    }

    #[test]
    fn invokes_registered_custom_validators_and_ignores_unknown_names() {
        let schema = json!({"code": {
            "type": "string",
            "custom_validator": "uppercase"
        }});
        let mut registry = ValidatorRegistry::default();
        registry.register("uppercase", |value, _rules| {
            if value
                .as_str()
                .is_some_and(|text| text == text.to_uppercase())
            {
                Ok(())
            } else {
                Err("Not upper".to_owned())
            }
        });
        assert!(validate_json_with_registry(&json!({"code": "ABC"}), &schema, &registry).is_ok());
        assert_eq!(
            validate_json_with_registry(&json!({"code": "Abc"}), &schema, &registry).unwrap_err(),
            "Not upper at code"
        );

        let unknown = json!({"code": {"custom_validator": "not_compiled"}});
        assert!(
            validate_json_with_registry(&json!({"code": "anything"}), &unknown, &registry).is_ok()
        );
    }
}
