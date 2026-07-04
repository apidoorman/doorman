#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RequestLogContext {
    pub request_id: String,
    pub method: String,
    pub path: String,
}
