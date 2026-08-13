use std::{
    collections::HashMap,
    env, fs,
    path::{Component, Path, PathBuf},
};

use aes_gcm::{
    Aes256Gcm, Nonce,
    aead::{Aead, Generate, KeyInit},
};
use hkdf::Hkdf;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::Sha256;
use thiserror::Error;
use time::{OffsetDateTime, format_description::well_known::Rfc3339};
use uuid::Uuid;

use crate::storage::runtime::{SharedStorage, StorageError};

const MAGIC: &[u8; 4] = b"DMP1";
const INFO: &[u8] = b"doorman-mem-dump-v1";

#[derive(Debug, Error)]
pub enum SnapshotError {
    #[error("{0}")]
    Storage(#[from] StorageError),
    #[error("MEM_ENCRYPTION_KEY must be set and at least 8 characters")]
    MissingKey,
    #[error("invalid or unsupported memory dump")]
    InvalidDump,
    #[error("memory dump encryption failed")]
    Encryption,
    #[error("memory dump path must stay within the configured dump directory")]
    InvalidPath,
    #[error("memory dump I/O failed: {0}")]
    Io(#[from] std::io::Error),
    #[error("memory dump JSON failed: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Serialize, Deserialize)]
struct Snapshot {
    version: u8,
    created_at: String,
    sanitized: bool,
    note: String,
    data: HashMap<String, Vec<Value>>,
}

pub async fn dump(
    storage: &SharedStorage,
    path_hint: Option<&str>,
) -> Result<PathBuf, SnapshotError> {
    let key_material = encryption_key()?;
    let data = storage.dump_memory_data().await?;
    let payload = Snapshot {
        version: 1,
        created_at: timestamp_iso(),
        sanitized: false,
        note: "Contains sensitive data; encrypted at rest with MEM_ENCRYPTION_KEY".to_owned(),
        data,
    };
    let plaintext = serde_json::to_vec(&payload)?;
    let salt = Uuid::new_v4().into_bytes();
    let key = derive_key(&key_material, &salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key).map_err(|_| SnapshotError::Encryption)?;
    let nonce = Nonce::generate();
    let ciphertext = cipher
        .encrypt(&nonce, plaintext.as_ref())
        .map_err(|_| SnapshotError::Encryption)?;

    let path = timestamped_path(path_hint)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut blob = Vec::with_capacity(32 + ciphertext.len());
    blob.extend_from_slice(MAGIC);
    blob.extend_from_slice(&salt);
    blob.extend_from_slice(&nonce);
    blob.extend_from_slice(&ciphertext);
    let temporary = path.with_extension("tmp");
    fs::write(&temporary, blob)?;
    fs::rename(&temporary, &path)?;
    Ok(path)
}

pub async fn restore(
    storage: &SharedStorage,
    path_hint: Option<&str>,
) -> Result<(u8, String), SnapshotError> {
    let key_material = encryption_key()?;
    let path = resolve_restore_path(path_hint)?.ok_or_else(|| {
        SnapshotError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "Dump file not found",
        ))
    })?;
    let blob = fs::read(path)?;
    let payload = decrypt_blob(&blob, &key_material)?;
    let version = payload.version;
    let created_at = payload.created_at.clone();
    storage.restore_memory_data(payload.data).await?;
    Ok((version, created_at))
}

fn decrypt_blob(blob: &[u8], key_material: &str) -> Result<Snapshot, SnapshotError> {
    if blob.len() < 32 || &blob[..4] != MAGIC {
        return Err(SnapshotError::InvalidDump);
    }
    let salt: [u8; 16] = blob[4..20]
        .try_into()
        .map_err(|_| SnapshotError::InvalidDump)?;
    let nonce = Nonce::try_from(&blob[20..32]).map_err(|_| SnapshotError::InvalidDump)?;
    let key = derive_key(key_material, &salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key).map_err(|_| SnapshotError::Encryption)?;
    let plaintext = cipher
        .decrypt(&nonce, &blob[32..])
        .map_err(|_| SnapshotError::InvalidDump)?;
    Ok(serde_json::from_slice(&plaintext)?)
}

fn derive_key(key_material: &str, salt: &[u8]) -> Result<[u8; 32], SnapshotError> {
    let hkdf = Hkdf::<Sha256>::new(Some(salt), key_material.as_bytes());
    let mut key = [0_u8; 32];
    hkdf.expand(INFO, &mut key)
        .map_err(|_| SnapshotError::Encryption)?;
    Ok(key)
}

fn encryption_key() -> Result<String, SnapshotError> {
    env::var("MEM_ENCRYPTION_KEY")
        .ok()
        .filter(|value| value.len() >= 8)
        .ok_or(SnapshotError::MissingKey)
}

fn default_path() -> PathBuf {
    env::var("MEM_DUMP_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("generated/memory_dump.bin"))
}

fn snapshot_directory() -> PathBuf {
    default_path()
        .parent()
        .filter(|path| !path.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf()
}

fn request_path(path_hint: Option<&str>) -> Result<PathBuf, SnapshotError> {
    let Some(value) = path_hint else {
        return Ok(default_path());
    };
    let hint = Path::new(value);
    let component_count = hint
        .components()
        .filter(|component| matches!(component, Component::Normal(_)))
        .count();
    if hint.is_absolute()
        || component_count > 1
        || hint.components().any(|component| {
            matches!(component, Component::ParentDir | Component::RootDir | Component::Prefix(_))
        })
    {
        return Err(SnapshotError::InvalidPath);
    }
    Ok(snapshot_directory().join(hint))
}

fn timestamped_path(path_hint: Option<&str>) -> Result<PathBuf, SnapshotError> {
    let hint = request_path(path_hint)?;
    let directory_hint = path_hint.is_some_and(|value| value.ends_with("/"));
    let (directory, stem) = if hint.is_dir() || directory_hint {
        (hint, "memory_dump".to_owned())
    } else {
        (
            hint.parent()
                .unwrap_or_else(|| Path::new("."))
                .to_path_buf(),
            hint.file_stem()
                .and_then(|value| value.to_str())
                .unwrap_or("memory_dump")
                .to_owned(),
        )
    };
    Ok(directory.join(format!("{stem}-{}.bin", timestamp_compact())))
}

fn is_regular_file(path: &Path) -> bool {
    fs::symlink_metadata(path)
        .map(|metadata| metadata.file_type().is_file())
        .unwrap_or(false)
}

fn resolve_restore_path(path_hint: Option<&str>) -> Result<Option<PathBuf>, SnapshotError> {
    let hint = request_path(path_hint)?;
    if is_regular_file(&hint) {
        return Ok(Some(hint));
    }
    let directory = if hint.is_dir() {
        hint.clone()
    } else {
        hint.parent()
            .unwrap_or_else(|| Path::new("."))
            .to_path_buf()
    };
    let stem = if path_hint.is_some_and(|value| value.ends_with("/")) {
        None
    } else {
        hint.file_stem()
            .and_then(|value| value.to_str())
            .map(str::to_owned)
    };
    let mut files = fs::read_dir(directory)
        .ok()
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .filter(|entry| {
            let name = entry.file_name().to_string_lossy().into_owned();
            entry.file_type().map(|kind| kind.is_file()).unwrap_or(false)
                && name.ends_with(".bin")
                && stem
                    .as_ref()
                    .is_none_or(|stem| name.starts_with(&format!("{stem}-")))
        })
        .collect::<Vec<_>>();
    files.sort_by_key(|entry| entry.metadata().and_then(|meta| meta.modified()).ok());
    Ok(files.pop().map(|entry| entry.path()))
}

fn timestamp_iso() -> String {
    OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_owned())
}

fn timestamp_compact() -> String {
    let now = OffsetDateTime::now_utc();
    format!(
        "{:04}{:02}{:02}T{:02}{:02}{:02}Z",
        now.year(),
        u8::from(now.month()),
        now.day(),
        now.hour(),
        now.minute(),
        now.second()
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn derives_the_python_compatible_key() {
        let key = derive_key("12345678", b"0123456789abcdef").unwrap();
        assert_eq!(key.len(), 32);
        assert_ne!(key, [0; 32]);
    }

    #[test]
    fn rejects_snapshot_paths_outside_the_configured_directory() {
        assert_eq!(
            request_path(Some("backup.bin")).unwrap(),
            PathBuf::from("generated/backup.bin")
        );
        for path in ["../backup.bin", "/tmp/backup.bin", "nested/backup.bin"] {
            assert!(matches!(request_path(Some(path)), Err(SnapshotError::InvalidPath)));
        }
    }

    #[test]
    fn decrypts_a_dump_created_by_the_python_backend() {
        use base64::Engine;

        let encoded = "RE1QMTAxMjM0NTY3ODlhYmNkZWZweXRob24tbm9uY2URWpMrOX++JWrZPCQ7vDZiPavCE/HhK9eZ94o5vRr7RV+fhZvWcjeN73XBh9VVn4lq7ftjeo+Uk7mCqZslCCpIyy4iutNThunPlKSvNhgfGc3czermqttHTWXW5Pvcjj+2sry/bfSUM6OQF1Z1JK4Faplxy0Bm/DOk11zJwPDY2PmGjDiUa23GixnceU17sdtVYSqY47N1+4/zy3EcWur4npCcP5HwJu1x7Fokz0xPImtWxMbf1l0Un6VyThjUJ0W1KP/YgvFb927zX8JJctVwlSLzRaFtZfzpoF5EPnZJ9FnALQl7PsYddN0V";
        let blob = base64::engine::general_purpose::STANDARD
            .decode(encoded)
            .unwrap();
        let snapshot = decrypt_blob(&blob, "fixture-key").unwrap();

        assert_eq!(snapshot.version, 1);
        assert_eq!(snapshot.created_at, "2026-08-06T12:34:56Z");
        assert_eq!(snapshot.data["users"][0]["username"], "fixture-admin");
        assert_eq!(snapshot.data["users"][0]["password"], "hash");
    }
}
