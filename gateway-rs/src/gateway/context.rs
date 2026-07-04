#[derive(Clone, Debug)]
pub struct GatewayContext {
    pub request_id: String,
    pub protocol: &'static str,
}
