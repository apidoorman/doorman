#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ApiCorsConfig {
    pub allow_origins: Option<Vec<String>>,
    pub allow_methods: Option<Vec<String>>,
    pub allow_headers: Option<Vec<String>>,
    pub allow_credentials: bool,
    pub expose_headers: Option<Vec<String>>,
}
