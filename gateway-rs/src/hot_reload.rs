use std::{
    collections::BTreeMap,
    env, fs,
    path::{Path, PathBuf},
    sync::RwLock,
};

use serde_json::{Map, Number, Value};

pub const RELOADABLE_KEYS: [&str; 22] = [
    "LOG_LEVEL",
    "LOG_FORMAT",
    "LOG_FILE",
    "GATEWAY_TIMEOUT",
    "UPSTREAM_TIMEOUT",
    "CONNECTION_TIMEOUT",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW",
    "CACHE_TTL",
    "CACHE_MAX_SIZE",
    "CIRCUIT_BREAKER_ENABLED",
    "CIRCUIT_BREAKER_THRESHOLD",
    "CIRCUIT_BREAKER_TIMEOUT",
    "RETRY_ENABLED",
    "RETRY_MAX_ATTEMPTS",
    "RETRY_BACKOFF",
    "METRICS_ENABLED",
    "METRICS_INTERVAL",
    "FEATURE_REQUEST_REPLAY",
    "FEATURE_AB_TESTING",
    "FEATURE_COST_ANALYTICS",
];

#[derive(Debug)]
pub struct HotReloadConfig {
    config_file: Option<PathBuf>,
    values: RwLock<BTreeMap<String, Value>>,
}

impl HotReloadConfig {
    pub fn from_env() -> Self {
        Self::new(env::var_os("DOORMAN_CONFIG_FILE").map(PathBuf::from))
    }

    pub fn new(config_file: Option<PathBuf>) -> Self {
        let manager = Self {
            config_file,
            values: RwLock::new(BTreeMap::new()),
        };
        manager.reload();
        manager
    }

    pub fn reload(&self) {
        let mut loaded = self
            .values
            .read()
            .map(|values| values.clone())
            .unwrap_or_default();
        if let Some(path) = self.config_file.as_deref()
            && path.exists()
            && let Ok(file_values) = load_file(path)
        {
            loaded.extend(file_values);
        }
        for key in RELOADABLE_KEYS {
            if let Ok(value) = env::var(key) {
                loaded.insert(key.to_owned(), parse_env_value(&value));
            }
        }
        if let Ok(mut values) = self.values.write() {
            *values = loaded;
        }
    }

    pub fn dump(&self) -> Value {
        let values = self
            .values
            .read()
            .map(|values| values.clone())
            .unwrap_or_default();
        Value::Object(values.into_iter().collect::<Map<_, _>>())
    }
}

fn load_file(path: &Path) -> Result<BTreeMap<String, Value>, String> {
    let contents = fs::read_to_string(path).map_err(|error| error.to_string())?;
    let value = match path.extension().and_then(|extension| extension.to_str()) {
        Some("yaml" | "yml") => {
            serde_yaml::from_str::<Value>(&contents).map_err(|error| error.to_string())?
        }
        Some("json") => serde_json::from_str(&contents).map_err(|error| error.to_string())?,
        Some(extension) => return Err(format!("Unsupported config file format: .{extension}")),
        None => return Err("Unsupported config file format".to_owned()),
    };
    let mut flattened = BTreeMap::new();
    flatten(&value, None, &mut flattened);
    Ok(flattened)
}

fn flatten(value: &Value, parent: Option<&str>, output: &mut BTreeMap<String, Value>) {
    let Value::Object(values) = value else {
        return;
    };
    for (key, value) in values {
        let key = parent.map_or_else(
            || key.to_ascii_uppercase(),
            |parent| format!("{parent}_{}", key.to_ascii_uppercase()),
        );
        if value.is_object() {
            flatten(value, Some(&key), output);
        } else {
            output.insert(key, value.clone());
        }
    }
}

fn parse_env_value(value: &str) -> Value {
    match value.to_ascii_lowercase().as_str() {
        "true" | "yes" | "1" => return Value::Bool(true),
        "false" | "no" | "0" => return Value::Bool(false),
        _ => {}
    }
    if let Ok(value) = value.parse::<i64>() {
        return Value::Number(Number::from(value));
    }
    if let Ok(value) = value.parse::<f64>()
        && let Some(value) = Number::from_f64(value)
    {
        return Value::Number(value);
    }
    Value::String(value.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn flattens_json_configuration_like_the_python_manager() {
        let directory =
            std::env::temp_dir().join(format!("doorman-hot-config-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&directory).unwrap();
        let path = directory.join("config.json");
        fs::write(
            &path,
            r#"{"gateway":{"timeout":45},"retry":{"enabled":true}}"#,
        )
        .unwrap();

        let config = HotReloadConfig::new(Some(path));
        let values = config.dump();
        assert_eq!(values["GATEWAY_TIMEOUT"], 45);
        assert_eq!(values["RETRY_ENABLED"], true);

        fs::remove_dir_all(directory).unwrap();
    }
}
