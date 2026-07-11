use std::fs;
use std::path::{Path, PathBuf};

use chrono::Utc;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use uuid::Uuid;

pub const WORKPROBA_DIR_NAME: &str = ".workproba";
const REGISTRY_FILE: &str = "registry.json";
const WORKSPACES_DIR: &str = "workspaces";
const SPACES_DIR: &str = "spaces";
const MANIFEST_FILE: &str = "manifest.json";
const CONVERSATIONS_DIR: &str = "conversations";
const VERSIONS_DIR: &str = "versions";
const REGISTRY_VERSION: u32 = 1;

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceInfo {
    pub id: String,
    pub folder_path: String,
    pub data_dir: String,
    pub title: String,
    pub created_at: String,
    pub last_opened_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ConversationSession {
    pub id: String,
    pub workspace_id: String,
    pub folder_path: String,
    pub title: String,
    pub messages: serde_json::Value,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reasoning_effort: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Registry {
    version: u32,
    workspaces: Vec<RegistryEntry>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct RegistryEntry {
    id: String,
    folder_path: String,
    folder_path_normalized: String,
    title: String,
    created_at: String,
    last_opened_at: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct WorkspaceManifest {
    id: String,
    folder_path: String,
    title: String,
    created_at: String,
    last_opened_at: String,
}

fn now_iso() -> String {
    Utc::now().to_rfc3339()
}

fn app_data_root(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_data_dir().map_err(|error| error.to_string())
}

/// Renomme `workspaces/` → `spaces/` une seule fois (T-V2-15b).
/// La structure interne `.workproba/` est conservée pour éviter de casser
/// les chemins existants ; le flatten canonique est reporté.
pub fn migrate_workspaces_to_spaces(app_data: &Path) -> Result<(), String> {
    let legacy = app_data.join(WORKSPACES_DIR);
    let spaces = app_data.join(SPACES_DIR);
    if legacy.is_dir() && !spaces.exists() {
        fs::rename(&legacy, &spaces).map_err(|error| {
            format!(
                "Impossible de migrer {WORKSPACES_DIR} vers {SPACES_DIR} : {error}"
            )
        })?;
    }
    Ok(())
}

fn ensure_spaces_migrated(app: &AppHandle) -> Result<PathBuf, String> {
    let root = app_data_root(app)?;
    migrate_workspaces_to_spaces(&root)?;
    Ok(root)
}

fn space_root(app: &AppHandle, space_id: &str) -> Result<PathBuf, String> {
    let app_data = ensure_spaces_migrated(app)?;
    let spaces_path = app_data.join(SPACES_DIR).join(space_id);
    if spaces_path.is_dir() {
        return Ok(spaces_path);
    }
    // Alias lecture : ancien chemin workspaces/{id}
    let legacy_path = app_data.join(WORKSPACES_DIR).join(space_id);
    if legacy_path.is_dir() {
        return Ok(legacy_path);
    }
    Ok(spaces_path)
}

fn registry_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(ensure_spaces_migrated(app)?.join(REGISTRY_FILE))
}

fn workspace_root(app: &AppHandle, workspace_id: &str) -> Result<PathBuf, String> {
    space_root(app, workspace_id)
}

pub fn workspace_data_dir(app: &AppHandle, workspace_id: &str) -> Result<PathBuf, String> {
    Ok(workspace_root(app, workspace_id)?.join(WORKPROBA_DIR_NAME))
}

fn workspace_title(folder_path: &Path) -> String {
    folder_path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("Workspace")
        .to_string()
}

pub fn normalize_folder_path(path: &Path) -> Result<String, String> {
    fs::canonicalize(path)
        .map_err(|error| format!("Impossible de résoudre le chemin : {error}"))
        .map(|canonical| canonical.to_string_lossy().to_string())
}

fn load_registry(app: &AppHandle) -> Result<Registry, String> {
    let _ = ensure_spaces_migrated(app)?;
    let path = registry_path(app)?;
    if !path.is_file() {
        return Ok(Registry {
            version: REGISTRY_VERSION,
            workspaces: Vec::new(),
        });
    }

    let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&raw).map_err(|error| error.to_string())
}

fn save_registry(app: &AppHandle, registry: &Registry) -> Result<(), String> {
    let path = registry_path(app)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let json = serde_json::to_string_pretty(registry).map_err(|error| error.to_string())?;
    fs::write(path, json).map_err(|error| error.to_string())
}

fn ensure_workspace_layout(app: &AppHandle, workspace_id: &str) -> Result<PathBuf, String> {
    let data_dir = workspace_data_dir(app, workspace_id)?;
    fs::create_dir_all(data_dir.join(CONVERSATIONS_DIR)).map_err(|error| error.to_string())?;
    fs::create_dir_all(data_dir.join(VERSIONS_DIR)).map_err(|error| error.to_string())?;
    Ok(data_dir)
}

fn write_manifest(data_dir: &Path, entry: &RegistryEntry) -> Result<(), String> {
    let manifest = WorkspaceManifest {
        id: entry.id.clone(),
        folder_path: entry.folder_path.clone(),
        title: entry.title.clone(),
        created_at: entry.created_at.clone(),
        last_opened_at: entry.last_opened_at.clone(),
    };
    let json = serde_json::to_string_pretty(&manifest).map_err(|error| error.to_string())?;
    fs::write(data_dir.join(MANIFEST_FILE), json).map_err(|error| error.to_string())
}

fn entry_to_info(app: &AppHandle, entry: &RegistryEntry) -> Result<WorkspaceInfo, String> {
    let data_dir = workspace_data_dir(app, &entry.id)?;
    Ok(WorkspaceInfo {
        id: entry.id.clone(),
        folder_path: entry.folder_path.clone(),
        data_dir: data_dir.to_string_lossy().to_string(),
        title: entry.title.clone(),
        created_at: entry.created_at.clone(),
        last_opened_at: entry.last_opened_at.clone(),
    })
}

pub fn lookup_workspace(app: &AppHandle, folder_path: &Path) -> Result<Option<WorkspaceInfo>, String> {
    if !folder_path.is_dir() {
        return Ok(None);
    }

    let normalized = normalize_folder_path(folder_path)?;
    let registry = load_registry(app)?;
    let entry = registry
        .workspaces
        .iter()
        .find(|entry| entry.folder_path_normalized == normalized);

    match entry {
        Some(entry) => entry_to_info(app, entry).map(Some),
        None => Ok(None),
    }
}

pub fn open_or_create_workspace(app: &AppHandle, folder_path: &Path) -> Result<WorkspaceInfo, String> {
    if !folder_path.is_dir() {
        return Err(format!(
            "Le dossier de l'espace n'existe pas : {}",
            folder_path.to_string_lossy()
        ));
    }

    let normalized = normalize_folder_path(folder_path)?;
    let folder_path_string = folder_path.to_string_lossy().to_string();
    let mut registry = load_registry(app)?;
    let now = now_iso();

    if let Some(entry) = registry
        .workspaces
        .iter_mut()
        .find(|entry| entry.folder_path_normalized == normalized)
    {
        entry.folder_path = folder_path_string.clone();
        entry.last_opened_at = now.clone();
        let entry_snapshot = entry.clone();
        let data_dir = ensure_workspace_layout(app, &entry_snapshot.id)?;
        write_manifest(&data_dir, &entry_snapshot)?;
        save_registry(app, &registry)?;
        return entry_to_info(app, &entry_snapshot);
    }

    let entry = RegistryEntry {
        id: format!("ws_{}", Uuid::new_v4().simple()),
        folder_path: folder_path_string,
        folder_path_normalized: normalized,
        title: workspace_title(folder_path),
        created_at: now.clone(),
        last_opened_at: now,
    };

    let data_dir = ensure_workspace_layout(app, &entry.id)?;
    write_manifest(&data_dir, &entry)?;
    registry.workspaces.push(entry.clone());
    save_registry(app, &registry)?;
    entry_to_info(app, &entry)
}

pub fn list_workspaces(app: &AppHandle) -> Result<Vec<WorkspaceInfo>, String> {
    let registry = load_registry(app)?;
    let mut workspaces: Vec<WorkspaceInfo> = registry
        .workspaces
        .iter()
        .filter_map(|entry| entry_to_info(app, entry).ok())
        .collect();
    workspaces.sort_by(|left, right| right.last_opened_at.cmp(&left.last_opened_at));
    Ok(workspaces)
}

pub fn get_workspace_data_dir_for_folder(
    app: &AppHandle,
    folder_path: &str,
) -> Result<Option<String>, String> {
    let normalized = normalize_folder_path(Path::new(folder_path))?;
    let registry = load_registry(app)?;
    let entry = registry
        .workspaces
        .iter()
        .find(|entry| entry.folder_path_normalized == normalized);
    Ok(entry.map(|entry| {
        workspace_data_dir(app, &entry.id)
            .map(|path| path.to_string_lossy().to_string())
            .unwrap_or_default()
    }))
}

fn conversation_path(data_dir: &Path, session_id: &str) -> PathBuf {
    data_dir.join(CONVERSATIONS_DIR).join(format!("{session_id}.json"))
}

pub fn list_conversations(app: &AppHandle, workspace_id: &str) -> Result<Vec<ConversationSession>, String> {
    let data_dir = workspace_data_dir(app, workspace_id)?;
    let conversations_dir = data_dir.join(CONVERSATIONS_DIR);
    if !conversations_dir.is_dir() {
        return Ok(Vec::new());
    }

    let mut sessions = Vec::new();
    for entry in fs::read_dir(conversations_dir).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
            continue;
        }
        let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
        if let Ok(session) = serde_json::from_str::<ConversationSession>(&raw) {
            sessions.push(session);
        }
    }

    sessions.sort_by(|left, right| right.updated_at.cmp(&left.updated_at));
    Ok(sessions)
}

pub fn get_conversation(
    app: &AppHandle,
    workspace_id: &str,
    session_id: &str,
) -> Result<Option<ConversationSession>, String> {
    let data_dir = workspace_data_dir(app, workspace_id)?;
    let path = conversation_path(&data_dir, session_id);
    if !path.is_file() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&raw)
        .map(Some)
        .map_err(|error| error.to_string())
}

pub fn find_conversation_by_id(
    app: &AppHandle,
    session_id: &str,
) -> Result<Option<ConversationSession>, String> {
    let registry = load_registry(app)?;
    for entry in &registry.workspaces {
        if let Some(session) = get_conversation(app, &entry.id, session_id)? {
            return Ok(Some(session));
        }
    }
    Ok(None)
}

pub fn save_conversation(app: &AppHandle, session: ConversationSession) -> Result<(), String> {
    let data_dir = ensure_workspace_layout(app, &session.workspace_id)?;
    let path = conversation_path(&data_dir, &session.id);
    let json = serde_json::to_string_pretty(&session).map_err(|error| error.to_string())?;
    fs::write(path, json).map_err(|error| error.to_string())
}

pub fn delete_conversation(
    app: &AppHandle,
    workspace_id: &str,
    session_id: &str,
) -> Result<(), String> {
    let data_dir = workspace_data_dir(app, workspace_id)?;
    let path = conversation_path(&data_dir, session_id);
    if path.is_file() {
        fs::remove_file(path).map_err(|error| error.to_string())?;
    }
    Ok(())
}

pub fn create_conversation(
    app: &AppHandle,
    workspace_id: &str,
    folder_path: &str,
    title: Option<String>,
) -> Result<ConversationSession, String> {
    let now = now_iso();
    let session = ConversationSession {
        id: format!(
            "sess_{}_{}",
            Utc::now().timestamp_millis(),
            &Uuid::new_v4().simple().to_string()[..7]
        ),
        workspace_id: workspace_id.to_string(),
        folder_path: folder_path.to_string(),
        title: title
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "Nouvelle conversation".to_string()),
        messages: serde_json::Value::Array(Vec::new()),
        reasoning_effort: None,
        model: None,
        summary: None,
        created_at: now.clone(),
        updated_at: now,
    };
    save_conversation(app, session.clone())?;
    Ok(session)
}

#[cfg(test)]
mod workspace_store_tests {
    use super::*;
    use std::fs;

    fn unique_temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "workproba_ws_test_{name}_{}",
            Uuid::new_v4().simple()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    #[test]
    fn migrate_workspaces_to_spaces_renames_directory() {
        let root = unique_temp_dir("rename");
        let legacy = root.join(WORKSPACES_DIR);
        let marker = legacy.join("ws_test").join(".workproba");
        fs::create_dir_all(&marker).expect("create legacy tree");
        fs::write(marker.join("manifest.json"), "{}").expect("write manifest");

        migrate_workspaces_to_spaces(&root).expect("migrate");

        let spaces = root.join(SPACES_DIR);
        assert!(spaces.is_dir());
        assert!(!legacy.exists());
        assert!(spaces.join("ws_test").join(".workproba").join("manifest.json").is_file());

        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_workspaces_to_spaces_is_idempotent_when_spaces_exists() {
        let root = unique_temp_dir("idempotent");
        let legacy = root.join(WORKSPACES_DIR);
        let spaces = root.join(SPACES_DIR);
        fs::create_dir_all(legacy.join("ws_a")).expect("legacy");
        fs::create_dir_all(spaces.join("ws_b")).expect("spaces");

        migrate_workspaces_to_spaces(&root).expect("migrate");

        assert!(legacy.is_dir());
        assert!(spaces.is_dir());

        let _ = fs::remove_dir_all(root);
    }
}
