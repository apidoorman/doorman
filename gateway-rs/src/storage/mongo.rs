use crate::config::SharedStorageConfig;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CollectionName {
    Users,
    Apis,
    Endpoints,
    Groups,
    Roles,
    Subscriptions,
    Routings,
    CreditDefs,
    UserCredits,
    Settings,
    Revocations,
}

impl CollectionName {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Users => "users",
            Self::Apis => "apis",
            Self::Endpoints => "endpoints",
            Self::Groups => "groups",
            Self::Roles => "roles",
            Self::Subscriptions => "subscriptions",
            Self::Routings => "routings",
            Self::CreditDefs => "credit_defs",
            Self::UserCredits => "user_credits",
            Self::Settings => "settings",
            Self::Revocations => "revocations",
        }
    }
}

#[derive(Clone, Debug)]
pub struct MongoRepositoryConfig {
    pub uri: String,
    pub database: String,
}

impl MongoRepositoryConfig {
    pub fn from_shared_config(config: &SharedStorageConfig) -> Self {
        Self {
            uri: config.mongo_uri(),
            database: config.mongo_database.clone(),
        }
    }
}
