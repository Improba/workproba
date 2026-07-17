use std::fs;
use std::path::{Path, PathBuf};

use chrono::Utc;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use uuid::Uuid;

use crate::commands::atomic_io::atomic_write;

pub const WORKPROBA_DIR_NAME: &str = ".workproba";
const REGISTRY_FILE: &str = "registry.json";
const WORKSPACES_DIR: &str = "workspaces";
const SPACES_DIR: &str = "spaces";
const MANIFEST_FILE: &str = "manifest.json";
const SPACE_MANIFEST_FILE: &str = "space.json";
const MEMORY_DB_FILE: &str = "memory.db";
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

/// Métadonnées V2 à la racine de l'espace (`app_data/spaces/{id}/space.json`).
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SpaceManifest {
    pub id: String,
    pub folder_path: String,
    pub title: String,
    pub created_at: String,
    pub last_opened_at: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub migrated_from_v1: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub migration_confirmed: Option<bool>,
}

fn now_iso() -> String {
    Utc::now().to_rfc3339()
}

/// Rejette les identifiants utilisés comme segment de chemin (`/`, `\`, `..`, vide).
fn validate_safe_path_segment_id(id: &str, label: &str) -> Result<(), String> {
    if id.trim().is_empty() {
        return Err(format!("{label} manquant"));
    }
    if id.contains('/') || id.contains('\\') {
        return Err(format!("{label} invalide : séparateurs interdits"));
    }
    if id.contains("..") {
        return Err(format!("{label} invalide : séquence .. interdite"));
    }
    Ok(())
}

fn validate_workspace_id(workspace_id: &str) -> Result<(), String> {
    validate_safe_path_segment_id(workspace_id, "Identifiant d'espace")
}

fn validate_session_id(session_id: &str) -> Result<(), String> {
    validate_safe_path_segment_id(session_id, "Identifiant de session")
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
            format!("Impossible de migrer {WORKSPACES_DIR} vers {SPACES_DIR} : {error}")
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
    validate_workspace_id(space_id)?;
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

fn normalize_workspace_title(title: &str) -> Result<String, String> {
    let trimmed = title.trim();
    if trimmed.is_empty() {
        return Err("Le nom de l'espace ne peut pas être vide.".to_string());
    }
    Ok(trimmed.to_string())
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
    let json = serde_json::to_string_pretty(registry).map_err(|error| error.to_string())?;
    atomic_write(&path, &json)
}

fn ensure_workspace_layout(app: &AppHandle, workspace_id: &str) -> Result<PathBuf, String> {
    let data_dir = workspace_data_dir(app, workspace_id)?;
    fs::create_dir_all(data_dir.join(CONVERSATIONS_DIR)).map_err(|error| error.to_string())?;
    fs::create_dir_all(data_dir.join(VERSIONS_DIR)).map_err(|error| error.to_string())?;
    Ok(data_dir)
}

fn space_manifest_path(space_root: &Path) -> PathBuf {
    space_root.join(SPACE_MANIFEST_FILE)
}

fn load_space_manifest(space_root: &Path) -> Result<Option<SpaceManifest>, String> {
    let path = space_manifest_path(space_root);
    if !path.is_file() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&raw)
        .map(Some)
        .map_err(|error| error.to_string())
}

fn write_space_manifest(space_root: &Path, manifest: &SpaceManifest) -> Result<(), String> {
    let json = serde_json::to_string_pretty(manifest).map_err(|error| error.to_string())?;
    atomic_write(&space_manifest_path(space_root), &json)
}

fn canonical_dest_exists(space_root: &Path) -> bool {
    space_root.join(MEMORY_DB_FILE).is_file() || space_root.join(VERSIONS_DIR).is_dir()
}

fn v1_migration_already_done(space_root: &Path) -> Result<bool, String> {
    if let Some(manifest) = load_space_manifest(space_root)? {
        if manifest.migrated_from_v1.unwrap_or(false) {
            return Ok(true);
        }
    }
    Ok(false)
}

fn merge_copy_tree(src: &Path, dst: &Path) -> Result<bool, String> {
    if !src.is_dir() {
        return Ok(false);
    }
    fs::create_dir_all(dst).map_err(|error| error.to_string())?;
    let mut copied = false;
    for entry in fs::read_dir(src).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let file_type = entry.file_type().map_err(|error| error.to_string())?;
        let target = dst.join(entry.file_name());
        if file_type.is_dir() {
            if merge_copy_tree(&entry.path(), &target)? {
                copied = true;
            }
        } else if !target.is_file() {
            fs::copy(entry.path(), &target).map_err(|error| error.to_string())?;
            copied = true;
        }
    }
    Ok(copied)
}

fn copy_file_if_absent(src: &Path, dst: &Path) -> Result<bool, String> {
    if !src.is_file() || dst.is_file() {
        return Ok(false);
    }
    if let Some(parent) = dst.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    fs::copy(src, dst).map_err(|error| error.to_string())?;
    Ok(true)
}

fn upsert_space_manifest(
    space_root: &Path,
    entry: &RegistryEntry,
    mark_migrated_from_v1: bool,
) -> Result<(), String> {
    let mut manifest = load_space_manifest(space_root)?.unwrap_or_else(|| SpaceManifest {
        id: entry.id.clone(),
        folder_path: entry.folder_path.clone(),
        title: entry.title.clone(),
        created_at: entry.created_at.clone(),
        last_opened_at: entry.last_opened_at.clone(),
        migrated_from_v1: None,
        migration_confirmed: None,
    });
    manifest.id = entry.id.clone();
    manifest.folder_path = entry.folder_path.clone();
    manifest.title = entry.title.clone();
    manifest.last_opened_at = entry.last_opened_at.clone();
    if mark_migrated_from_v1 {
        manifest.migrated_from_v1 = Some(true);
        manifest.migration_confirmed = Some(false);
    }
    write_space_manifest(space_root, &manifest)
}

/// Migration V1→V2 : copie `versions/` et `memory.db` vers la racine canonique de l'espace.
/// Les fichiers source ne sont jamais supprimés (rollback possible).
fn migrate_v1_to_v2_paths(
    app_data: &Path,
    space_id: &str,
    client_folder_path: &Path,
    entry: &RegistryEntry,
) -> Result<(), String> {
    migrate_workspaces_to_spaces(app_data)?;
    let space_root = app_data.join(SPACES_DIR).join(space_id);
    fs::create_dir_all(&space_root).map_err(|error| error.to_string())?;

    if v1_migration_already_done(&space_root)? {
        return upsert_space_manifest(&space_root, entry, false);
    }

    // Toujours tenter les copies idempotentes avant de poser le flag, y compris
    // quand la destination existe déjà (migration partielle ou installs sans flag).
    let nested_workproba = space_root.join(WORKPROBA_DIR_NAME);
    let client_workproba = client_folder_path.join(WORKPROBA_DIR_NAME);
    let canonical_versions = space_root.join(VERSIONS_DIR);
    let canonical_memory = space_root.join(MEMORY_DB_FILE);

    let mut did_migrate = false;
    for src in [
        client_workproba.join(VERSIONS_DIR),
        nested_workproba.join(VERSIONS_DIR),
    ] {
        if merge_copy_tree(&src, &canonical_versions)? {
            did_migrate = true;
        }
    }
    for src in [
        client_workproba.join(MEMORY_DB_FILE),
        nested_workproba.join(MEMORY_DB_FILE),
    ] {
        if copy_file_if_absent(&src, &canonical_memory)? {
            did_migrate = true;
        }
    }

    let mark_done = did_migrate || canonical_dest_exists(&space_root);
    upsert_space_manifest(&space_root, entry, mark_done)
}

pub fn migrate_v1_to_v2(
    app: &AppHandle,
    space_id: &str,
    client_folder_path: &Path,
) -> Result<(), String> {
    let app_data = ensure_spaces_migrated(app)?;
    let registry = load_registry(app)?;
    let entry = registry
        .workspaces
        .iter()
        .find(|entry| entry.id == space_id)
        .ok_or_else(|| format!("Espace introuvable : {space_id}"))?
        .clone();
    migrate_v1_to_v2_paths(&app_data, space_id, client_folder_path, &entry)
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
    atomic_write(&data_dir.join(MANIFEST_FILE), &json)
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

pub fn lookup_workspace(
    app: &AppHandle,
    folder_path: &Path,
) -> Result<Option<WorkspaceInfo>, String> {
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

pub fn open_or_create_workspace(
    app: &AppHandle,
    folder_path: &Path,
) -> Result<WorkspaceInfo, String> {
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
        save_registry(app, &registry)?;
        let app_data = ensure_spaces_migrated(app)?;
        migrate_v1_to_v2_paths(
            &app_data,
            &entry_snapshot.id,
            folder_path,
            &entry_snapshot,
        )?;
        write_manifest(&data_dir, &entry_snapshot)?;
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
    registry.workspaces.push(entry.clone());
    save_registry(app, &registry)?;
    let app_data = ensure_spaces_migrated(app)?;
    migrate_v1_to_v2_paths(&app_data, &entry.id, folder_path, &entry)?;
    write_manifest(&data_dir, &entry)?;
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

pub fn update_workspace_title(
    app: &AppHandle,
    workspace_id: &str,
    title: &str,
) -> Result<WorkspaceInfo, String> {
    validate_workspace_id(workspace_id)?;
    let trimmed = normalize_workspace_title(title)?;

    let mut registry = load_registry(app)?;
    let entry = registry
        .workspaces
        .iter_mut()
        .find(|entry| entry.id == workspace_id)
        .ok_or_else(|| format!("Espace introuvable : {workspace_id}"))?;

    entry.title = trimmed.to_string();
    let entry_snapshot = entry.clone();
    let data_dir = workspace_data_dir(app, workspace_id)?;
    if data_dir.is_dir() {
        write_manifest(&data_dir, &entry_snapshot)?;
    }
    save_registry(app, &registry)?;
    entry_to_info(app, &entry_snapshot)
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
    match entry {
        Some(entry) => {
            let path = workspace_data_dir(app, &entry.id)?;
            Ok(Some(path.to_string_lossy().to_string()))
        }
        None => Ok(None),
    }
}

fn conversation_path(data_dir: &Path, session_id: &str) -> Result<PathBuf, String> {
    validate_session_id(session_id)?;
    Ok(data_dir
        .join(CONVERSATIONS_DIR)
        .join(format!("{session_id}.json")))
}

pub fn list_conversations(
    app: &AppHandle,
    workspace_id: &str,
) -> Result<Vec<ConversationSession>, String> {
    validate_workspace_id(workspace_id)?;
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
    validate_workspace_id(workspace_id)?;
    let data_dir = workspace_data_dir(app, workspace_id)?;
    let path = conversation_path(&data_dir, session_id)?;
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
    validate_session_id(session_id)?;
    let registry = load_registry(app)?;
    for entry in &registry.workspaces {
        if let Some(session) = get_conversation(app, &entry.id, session_id)? {
            return Ok(Some(session));
        }
    }
    Ok(None)
}

pub fn save_conversation(app: &AppHandle, session: ConversationSession) -> Result<(), String> {
    validate_workspace_id(&session.workspace_id)?;
    validate_session_id(&session.id)?;
    let data_dir = ensure_workspace_layout(app, &session.workspace_id)?;
    let path = conversation_path(&data_dir, &session.id)?;
    let json = serde_json::to_string_pretty(&session).map_err(|error| error.to_string())?;
    atomic_write(&path, &json)
}

pub fn delete_conversation(
    app: &AppHandle,
    workspace_id: &str,
    session_id: &str,
) -> Result<(), String> {
    validate_workspace_id(workspace_id)?;
    let data_dir = workspace_data_dir(app, workspace_id)?;
    let path = conversation_path(&data_dir, session_id)?;
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
    validate_workspace_id(workspace_id)?;
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
        assert!(spaces
            .join("ws_test")
            .join(".workproba")
            .join("manifest.json")
            .is_file());

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

    #[test]
    fn normalize_workspace_title_trims_and_rejects_empty() {
        assert_eq!(
            normalize_workspace_title("  Client Dupont  ").expect("trim"),
            "Client Dupont"
        );
        assert!(normalize_workspace_title("   ").is_err());
        assert!(normalize_workspace_title("").is_err());
    }

    fn registry_entry(id: &str, folder: &Path) -> RegistryEntry {
        RegistryEntry {
            id: id.to_string(),
            folder_path: folder.to_string_lossy().to_string(),
            folder_path_normalized: folder.to_string_lossy().to_string(),
            title: "Test Space".to_string(),
            created_at: "2026-01-01T00:00:00Z".to_string(),
            last_opened_at: "2026-01-02T00:00:00Z".to_string(),
        }
    }

    #[test]
    fn migrate_v1_to_v2_copies_client_versions_and_memory() {
        let app_data = unique_temp_dir("v1_client");
        let client = unique_temp_dir("v1_client_project");
        let space_id = "ws_test_client";
        let client_wp = client.join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(client_wp.join(VERSIONS_DIR).join("sess_a")).expect("versions");
        fs::write(
            client_wp.join(VERSIONS_DIR).join("sess_a").join("file.txt"),
            "v1",
        )
        .expect("version file");
        fs::write(client_wp.join(MEMORY_DB_FILE), "sqlite-memory").expect("memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        let space_root = app_data.join(SPACES_DIR).join(space_id);
        assert!(space_root
            .join(VERSIONS_DIR)
            .join("sess_a")
            .join("file.txt")
            .is_file());
        assert!(space_root.join(MEMORY_DB_FILE).is_file());
        assert!(client_wp.join(MEMORY_DB_FILE).is_file());

        let manifest: SpaceManifest = serde_json::from_str(
            &fs::read_to_string(space_root.join(SPACE_MANIFEST_FILE)).unwrap(),
        )
        .expect("space.json");
        assert_eq!(manifest.migrated_from_v1, Some(true));
        assert_eq!(manifest.migration_confirmed, Some(false));

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_copies_nested_app_data_workproba() {
        let app_data = unique_temp_dir("v1_nested");
        let client = unique_temp_dir("v1_nested_project");
        let space_id = "ws_test_nested";
        let nested = app_data
            .join(SPACES_DIR)
            .join(space_id)
            .join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(nested.join(VERSIONS_DIR).join("hash_abc")).expect("versions");
        fs::write(
            nested.join(VERSIONS_DIR).join("hash_abc").join("doc.md"),
            "nested",
        )
        .expect("version file");
        fs::write(nested.join(MEMORY_DB_FILE), "nested-db").expect("memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        let space_root = app_data.join(SPACES_DIR).join(space_id);
        assert!(space_root
            .join(VERSIONS_DIR)
            .join("hash_abc")
            .join("doc.md")
            .is_file());
        assert_eq!(
            fs::read_to_string(space_root.join(MEMORY_DB_FILE)).expect("read"),
            "nested-db"
        );
        assert!(nested.join(MEMORY_DB_FILE).is_file());

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_skips_when_flag_set() {
        let app_data = unique_temp_dir("v1_skip_flag");
        let client = unique_temp_dir("v1_skip_flag_project");
        let space_id = "ws_test_skip";
        let space_root = app_data.join(SPACES_DIR).join(space_id);
        fs::create_dir_all(&space_root).expect("space root");
        let manifest = SpaceManifest {
            id: space_id.to_string(),
            folder_path: client.to_string_lossy().to_string(),
            title: "Test".to_string(),
            created_at: "2026-01-01T00:00:00Z".to_string(),
            last_opened_at: "2026-01-01T00:00:00Z".to_string(),
            migrated_from_v1: Some(true),
            migration_confirmed: Some(false),
        };
        write_space_manifest(&space_root, &manifest).expect("write manifest");

        let client_wp = client.join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(&client_wp).expect("client wp");
        fs::write(client_wp.join(MEMORY_DB_FILE), "should-not-copy").expect("memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        assert!(!space_root.join(MEMORY_DB_FILE).is_file());

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_completes_partial_migration() {
        let app_data = unique_temp_dir("v1_partial");
        let client = unique_temp_dir("v1_partial_project");
        let space_id = "ws_test_partial";
        let space_root = app_data.join(SPACES_DIR).join(space_id);
        // Destination partielle : versions déjà là, memory encore absente
        fs::create_dir_all(space_root.join(VERSIONS_DIR).join("sess_a")).expect("versions");
        fs::write(
            space_root.join(VERSIONS_DIR).join("sess_a").join("a.txt"),
            "already",
        )
        .expect("version file");

        let client_wp = client.join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(client_wp.join(VERSIONS_DIR).join("sess_b")).expect("client versions");
        fs::write(
            client_wp.join(VERSIONS_DIR).join("sess_b").join("b.txt"),
            "pending",
        )
        .expect("client version");
        fs::write(client_wp.join(MEMORY_DB_FILE), "db-v1").expect("client memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        assert!(space_root
            .join(VERSIONS_DIR)
            .join("sess_b")
            .join("b.txt")
            .is_file());
        assert_eq!(
            fs::read_to_string(space_root.join(MEMORY_DB_FILE)).expect("memory"),
            "db-v1"
        );
        let manifest: SpaceManifest = serde_json::from_str(
            &fs::read_to_string(space_root.join(SPACE_MANIFEST_FILE)).unwrap(),
        )
        .expect("space.json");
        assert_eq!(manifest.migrated_from_v1, Some(true));

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_repairs_flag_when_dest_exists_without_flag() {
        let app_data = unique_temp_dir("v1_repair_flag");
        let client = unique_temp_dir("v1_repair_flag_project");
        let space_id = "ws_test_repair";
        let space_root = app_data.join(SPACES_DIR).join(space_id);
        fs::create_dir_all(space_root.join(VERSIONS_DIR)).expect("versions");
        fs::write(space_root.join(MEMORY_DB_FILE), "existing").expect("memory");

        let client_wp = client.join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(&client_wp).expect("client wp");
        fs::write(client_wp.join(MEMORY_DB_FILE), "new-db").expect("client memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        assert_eq!(
            fs::read_to_string(space_root.join(MEMORY_DB_FILE)).expect("read"),
            "existing"
        );
        let manifest: SpaceManifest = serde_json::from_str(
            &fs::read_to_string(space_root.join(SPACE_MANIFEST_FILE)).unwrap(),
        )
        .expect("space.json");
        assert_eq!(manifest.migrated_from_v1, Some(true));

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_skips_when_destination_exists() {
        let app_data = unique_temp_dir("v1_skip_dest");
        let client = unique_temp_dir("v1_skip_dest_project");
        let space_id = "ws_test_dest";
        let space_root = app_data.join(SPACES_DIR).join(space_id);
        fs::create_dir_all(space_root.join(VERSIONS_DIR)).expect("versions");
        fs::write(space_root.join(MEMORY_DB_FILE), "existing").expect("memory");

        let client_wp = client.join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(&client_wp).expect("client wp");
        fs::write(client_wp.join(MEMORY_DB_FILE), "new-db").expect("client memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        assert_eq!(
            fs::read_to_string(space_root.join(MEMORY_DB_FILE)).expect("read"),
            "existing"
        );
        let manifest: SpaceManifest = serde_json::from_str(
            &fs::read_to_string(space_root.join(SPACE_MANIFEST_FILE)).unwrap(),
        )
        .expect("space.json");
        assert_eq!(manifest.migrated_from_v1, Some(true));

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_repairs_flag_is_idempotent() {
        let app_data = unique_temp_dir("v1_repair_idem");
        let client = unique_temp_dir("v1_repair_idem_project");
        let space_id = "ws_test_repair_idem";
        let space_root = app_data.join(SPACES_DIR).join(space_id);
        fs::create_dir_all(space_root.join(VERSIONS_DIR)).expect("versions");
        fs::write(space_root.join(MEMORY_DB_FILE), "existing").expect("memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate1");
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate2");

        assert_eq!(
            fs::read_to_string(space_root.join(MEMORY_DB_FILE)).expect("read"),
            "existing"
        );

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn validate_workspace_and_session_ids_reject_traversal() {
        assert!(validate_workspace_id("ws_abc123").is_ok());
        assert!(validate_workspace_id("../etc").is_err());
        assert!(validate_workspace_id("ws/evil").is_err());
        assert!(validate_workspace_id("").is_err());

        assert!(validate_session_id("sess_123_abc").is_ok());
        assert!(validate_session_id("..").is_err());
        assert!(validate_session_id("sess/evil").is_err());
    }

    #[test]
    fn new_space_migrate_succeeds_after_registry_saved() {
        let app_data = unique_temp_dir("registry_before_migrate");
        let client = unique_temp_dir("registry_before_migrate_client");
        let space_id = "ws_test_new_registry";
        let entry = registry_entry(space_id, &client);

        let registry = Registry {
            version: REGISTRY_VERSION,
            workspaces: vec![entry.clone()],
        };
        fs::create_dir_all(&app_data).expect("mkdir app_data");
        let json = serde_json::to_string_pretty(&registry).expect("serialize registry");
        fs::write(app_data.join(REGISTRY_FILE), json).expect("write registry");

        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate");

        let space_root = app_data.join(SPACES_DIR).join(space_id);
        assert!(space_root.join(SPACE_MANIFEST_FILE).is_file());

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }

    #[test]
    fn migrate_v1_to_v2_is_idempotent() {
        let app_data = unique_temp_dir("v1_idempotent");
        let client = unique_temp_dir("v1_idempotent_project");
        let space_id = "ws_test_idem";
        let client_wp = client.join(WORKPROBA_DIR_NAME);
        fs::create_dir_all(&client_wp).expect("client wp");
        fs::write(client_wp.join(MEMORY_DB_FILE), "db-v1").expect("memory");

        let entry = registry_entry(space_id, &client);
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate1");
        migrate_v1_to_v2_paths(&app_data, space_id, &client, &entry).expect("migrate2");

        let space_root = app_data.join(SPACES_DIR).join(space_id);
        assert_eq!(
            fs::read_to_string(space_root.join(MEMORY_DB_FILE)).expect("read"),
            "db-v1"
        );

        let _ = fs::remove_dir_all(app_data);
        let _ = fs::remove_dir_all(client);
    }
}
