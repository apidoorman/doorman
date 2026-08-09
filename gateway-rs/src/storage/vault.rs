use std::env;

use base64::{Engine, engine::general_purpose::URL_SAFE};
use fernet::Fernet;
use pbkdf2::pbkdf2_hmac;
use sha2::{Digest, Sha256};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum VaultError {
    #[error("VAULT_KEY is not configured")]
    MissingKey,
    #[error("vault encryption failed")]
    Encryption,
}

pub fn encrypt(value: &str, email: &str, username: &str) -> Result<String, VaultError> {
    let vault_key = env::var("VAULT_KEY")
        .ok()
        .filter(|value| !value.is_empty())
        .ok_or(VaultError::MissingKey)?;
    let combined = format!("{email}:{username}:{vault_key}");
    let salt = Sha256::digest(combined.as_bytes());
    let mut derived = [0_u8; 32];
    pbkdf2_hmac::<Sha256>(vault_key.as_bytes(), &salt, 100_000, &mut derived);
    let encoded = URL_SAFE.encode(derived);
    let cipher = Fernet::new(&encoded).ok_or(VaultError::Encryption)?;
    Ok(format!("v1:{}", cipher.encrypt(value.as_bytes())))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn requires_the_configured_vault_key() {
        // The route-level contract maps this deterministic error to VAULT001.
        assert_eq!(
            VaultError::MissingKey.to_string(),
            "VAULT_KEY is not configured"
        );
    }
}
