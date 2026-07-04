#[derive(Clone, Debug)]
pub struct AuditEvent {
    pub action: String,
    pub target: String,
    pub status: String,
}
