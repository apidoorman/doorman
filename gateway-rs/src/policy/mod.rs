pub mod auth;
pub mod bandwidth;
pub mod credits;
pub mod groups;
pub mod ip;
pub mod quota;
pub mod rate_limit;
pub mod roles;
pub mod subscription;
pub mod throttle;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PolicyStage {
    Ip,
    Subscription,
    Group,
    RateLimit,
    Authentication,
    Role,
    Bandwidth,
    Credits,
}
