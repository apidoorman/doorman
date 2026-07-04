use std::env;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BodyLimits {
    pub default: usize,
    pub rest: usize,
    pub soap: usize,
    pub graphql: usize,
    pub grpc: usize,
}

impl BodyLimits {
    pub fn from_env() -> Self {
        let default = env_usize("MAX_BODY_SIZE_BYTES", 1024 * 1024);
        Self {
            default,
            rest: env_usize("MAX_BODY_SIZE_BYTES_REST", default),
            soap: env_usize("MAX_BODY_SIZE_BYTES_SOAP", default),
            graphql: env_usize("MAX_BODY_SIZE_BYTES_GRAPHQL", default),
            grpc: env_usize("MAX_BODY_SIZE_BYTES_GRPC", default),
        }
    }
}

fn env_usize(name: &str, default: usize) -> usize {
    env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}
