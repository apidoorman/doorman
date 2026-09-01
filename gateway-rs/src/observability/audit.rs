#[derive(Clone, Debug)]
pub struct AuditEvent {
    pub action: String,
    pub target: String,
    pub status: String,
}

pub fn global_ip_deny(target: &str, reason: &str, xff: Option<&str>, source_ip: Option<&str>) {
    tracing::info!(
        action = "ip.global_deny",
        target,
        status = "blocked",
        reason,
        xff,
        source_ip,
        "platform audit event"
    );
}
