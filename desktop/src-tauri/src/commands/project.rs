use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;

use super::fs_watch::start_fs_watch;
use super::settings_store::get_app_settings;
use super::workspace_store::{self, ConversationSession, WorkspaceInfo, WORKPROBA_DIR_NAME};

const LAST_PROJECT_FILE: &str = "last-project.json";

#[derive(Default)]
pub struct ProjectState {
    pub active_path: Mutex<Option<PathBuf>>,
    pub active_workspace_id: Mutex<Option<String>>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct LastProjectConfig {
    project_path: String,
    workspace_id: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct DocumentEntry {
    pub name: String,
    pub relative_path: String,
    pub kind: String,
}

fn classify_document(path: &Path) -> String {
    match path
        .extension()
        .and_then(|ext| ext.to_str())
        .map(str::to_ascii_lowercase)
    {
        Some(ext) if matches!(ext.as_str(), "xls" | "xlsx" | "csv") => "table".to_string(),
        Some(ext) if matches!(ext.as_str(), "doc" | "docx" | "ppt" | "pptx") => {
            "report".to_string()
        }
        Some(ext) if matches!(ext.as_str(), "pdf") => "source".to_string(),
        _ => "other".to_string(),
    }
}

fn is_hidden(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.starts_with('.'))
}

fn collect_documents(
    project_root: &Path,
    current_dir: &Path,
    entries: &mut Vec<DocumentEntry>,
) -> Result<(), String> {
    let read_dir = fs::read_dir(current_dir).map_err(|error| error.to_string())?;

    for entry in read_dir {
        let entry = entry.map_err(|error| error.to_string())?;
        let path = entry.path();

        if is_hidden(&path) {
            continue;
        }

        let metadata = entry.metadata().map_err(|error| error.to_string())?;
        if metadata.is_dir() {
            collect_documents(project_root, &path, entries)?;
            continue;
        }

        if !metadata.is_file() {
            continue;
        }

        let relative_path = path
            .strip_prefix(project_root)
            .map_err(|error| error.to_string())?
            .to_string_lossy()
            .replace('\\', "/");

        entries.push(DocumentEntry {
            name: path
                .file_name()
                .and_then(|name| name.to_str())
                .unwrap_or_default()
                .to_string(),
            relative_path,
            kind: classify_document(&path),
        });
    }

    Ok(())
}

fn activate_workspace(
    app: &AppHandle,
    state: &State<'_, ProjectState>,
    path: &Path,
) -> Result<WorkspaceInfo, String> {
    let workspace = workspace_store::open_or_create_workspace(app, path)?;
    persist_last_project_path(app, &workspace)?;

    let mut active_path = state
        .active_path
        .lock()
        .map_err(|_| "Impossible de verrouiller l'état de l'espace".to_string())?;
    *active_path = Some(path.to_path_buf());

    let mut active_workspace_id = state
        .active_workspace_id
        .lock()
        .map_err(|_| "Impossible de verrouiller l'état workspace".to_string())?;
    *active_workspace_id = Some(workspace.id.clone());

    start_fs_watch(app, path);

    Ok(workspace)
}

fn pick_space_folder_title(app: &AppHandle) -> &'static str {
    match get_app_settings(app.clone())
        .ok()
        .and_then(|settings| settings.locale)
        .as_deref()
    {
        Some("fr") => "Ouvrir un espace…",
        _ => "Open a space…",
    }
}

#[tauri::command]
pub async fn pick_project_folder(app: AppHandle) -> Result<Option<String>, String> {
    let selection = app
        .dialog()
        .file()
        .set_title(pick_space_folder_title(&app))
        .blocking_pick_folder();

    Ok(selection.map(|path| path.to_string()))
}

#[tauri::command]
pub fn set_active_project_path(
    app: AppHandle,
    state: State<'_, ProjectState>,
    project_path: String,
) -> Result<WorkspaceInfo, String> {
    let path = PathBuf::from(&project_path);
    activate_workspace(&app, &state, &path)
}

#[tauri::command]
pub fn get_active_project_path(state: State<'_, ProjectState>) -> Result<Option<String>, String> {
    let active_path = state
        .active_path
        .lock()
        .map_err(|_| "Impossible de verrouiller l'état de l'espace".to_string())?;

    Ok(active_path
        .as_ref()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
pub fn get_workspace_info(
    app: AppHandle,
    project_path: String,
) -> Result<Option<WorkspaceInfo>, String> {
    let path = PathBuf::from(&project_path);
    workspace_store::lookup_workspace(&app, &path)
}

#[tauri::command]
pub fn get_workspace_data_dir(
    app: AppHandle,
    project_path: String,
) -> Result<Option<String>, String> {
    workspace_store::get_workspace_data_dir_for_folder(&app, &project_path)
}

#[tauri::command]
pub fn list_workspaces(app: AppHandle) -> Result<Vec<WorkspaceInfo>, String> {
    workspace_store::list_workspaces(&app)
}

#[tauri::command]
pub fn update_workspace_title(
    app: AppHandle,
    workspace_id: String,
    title: String,
) -> Result<WorkspaceInfo, String> {
    workspace_store::update_workspace_title(&app, &workspace_id, &title)
}

#[tauri::command]
pub fn list_conversations(
    app: AppHandle,
    workspace_id: String,
) -> Result<Vec<ConversationSession>, String> {
    workspace_store::list_conversations(&app, &workspace_id)
}

#[tauri::command]
pub fn get_conversation(
    app: AppHandle,
    workspace_id: String,
    session_id: String,
) -> Result<Option<ConversationSession>, String> {
    workspace_store::get_conversation(&app, &workspace_id, &session_id)
}

#[tauri::command]
pub fn find_conversation_by_id(
    app: AppHandle,
    session_id: String,
) -> Result<Option<ConversationSession>, String> {
    workspace_store::find_conversation_by_id(&app, &session_id)
}

#[tauri::command]
pub fn save_conversation(app: AppHandle, session: ConversationSession) -> Result<(), String> {
    workspace_store::save_conversation(&app, session)
}

#[tauri::command]
pub fn delete_conversation(
    app: AppHandle,
    workspace_id: String,
    session_id: String,
) -> Result<(), String> {
    workspace_store::delete_conversation(&app, &workspace_id, &session_id)
}

#[tauri::command]
pub fn create_conversation(
    app: AppHandle,
    workspace_id: String,
    folder_path: String,
    title: Option<String>,
) -> Result<ConversationSession, String> {
    workspace_store::create_conversation(&app, &workspace_id, &folder_path, title)
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct DirEntry {
    pub name: String,
    pub relative_path: String,
    pub is_dir: bool,
    pub kind: String,
}

fn icon_kind(path: &Path) -> String {
    if path.is_dir() {
        return "folder".to_string();
    }
    match path
        .extension()
        .and_then(|ext| ext.to_str())
        .map(str::to_ascii_lowercase)
    {
        Some(ext) if matches!(ext.as_str(), "xls" | "xlsx" | "csv" | "ods") => {
            "spreadsheet".to_string()
        }
        Some(ext) if matches!(ext.as_str(), "doc" | "docx" | "odt" | "rtf") => {
            "document".to_string()
        }
        Some(ext) if matches!(ext.as_str(), "ppt" | "pptx" | "odp") => "presentation".to_string(),
        Some(ext) if matches!(ext.as_str(), "pdf") => "pdf".to_string(),
        Some(ext)
            if matches!(
                ext.as_str(),
                "png" | "jpg" | "jpeg" | "gif" | "webp" | "svg" | "bmp"
            ) =>
        {
            "image".to_string()
        }
        Some(ext) if matches!(ext.as_str(), "md" | "txt" | "rst") => "text".to_string(),
        Some(ext)
            if matches!(
                ext.as_str(),
                "js" | "ts"
                    | "tsx"
                    | "jsx"
                    | "py"
                    | "rs"
                    | "go"
                    | "java"
                    | "c"
                    | "cpp"
                    | "h"
                    | "json"
                    | "yaml"
                    | "yml"
                    | "toml"
                    | "sh"
                    | "html"
                    | "css"
                    | "scss"
                    | "vue"
            ) =>
        {
            "code".to_string()
        }
        Some(ext) if matches!(ext.as_str(), "zip" | "tar" | "gz" | "rar" | "7z") => {
            "archive".to_string()
        }
        _ => "file".to_string(),
    }
}

/// Liste un seul niveau d'un dossier du workspace (lazy expand).
/// `dir_relative_path` est vide pour la racine du workspace.
#[tauri::command]
pub fn list_dir_entries(
    project_path: String,
    dir_relative_path: String,
) -> Result<Vec<DirEntry>, String> {
    log::info!(
        "list_dir_entries appelée: project_path={project_path:?}, dir_relative_path={dir_relative_path:?}"
    );
    let project_root = PathBuf::from(&project_path);
    if !project_root.is_dir() {
        log::warn!("list_dir_entries: pas un dossier: {project_path:?}");
        return Err(format!(
            "Le dossier de l'espace n'existe pas : {project_path}"
        ));
    }

    let target_dir = if dir_relative_path.is_empty() {
        project_root.clone()
    } else {
        // On refuse tout chemin qui sortirait de la racine (sécurité + cohérence).
        let candidate = project_root.join(&dir_relative_path);
        let canonical = candidate.canonicalize().map_err(|e| {
            log::warn!("list_dir_entries: canonicalize candidate échoué: {e}");
            e.to_string()
        })?;
        let root_canonical = project_root.canonicalize().map_err(|e| {
            log::warn!("list_dir_entries: canonicalize root échoué: {e}");
            e.to_string()
        })?;
        if !canonical.starts_with(&root_canonical) {
            log::warn!("list_dir_entries: chemin hors workspace");
            return Err("Chemin hors du workspace".to_string());
        }
        canonical
    };

    let read_dir = fs::read_dir(&target_dir).map_err(|e| {
        log::warn!("list_dir_entries: read_dir échoué sur {target_dir:?}: {e}");
        e.to_string()
    })?;
    let mut entries: Vec<DirEntry> = Vec::new();

    for entry in read_dir {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();

        if is_hidden(&path) {
            continue;
        }

        let metadata = entry.metadata().map_err(|e| e.to_string())?;
        let is_dir = metadata.is_dir();
        if !is_dir && !metadata.is_file() {
            continue;
        }

        let relative_path = path
            .strip_prefix(&project_root)
            .map_err(|e| e.to_string())?
            .to_string_lossy()
            .replace('\\', "/");

        entries.push(DirEntry {
            name: path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or_default()
                .to_string(),
            relative_path,
            is_dir,
            kind: icon_kind(&path),
        });
    }

    // Dossiers d'abord, puis fichiers ; tri insensible à la casse.
    entries.sort_by(|a, b| match (a.is_dir, b.is_dir) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a
            .name
            .to_ascii_lowercase()
            .cmp(&b.name.to_ascii_lowercase()),
    });

    log::info!(
        "list_dir_entries: {} entrée(s) pour dir_relative_path={dir_relative_path:?}",
        entries.len()
    );
    Ok(entries)
}

/// Révèle un chemin dans le gestionnaire de fichiers de l'OS.
#[tauri::command]
pub fn reveal_in_os(path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(&path);
    if !path_buf.exists() {
        return Err(format!("Le chemin n'existe pas : {path}"));
    }

    #[cfg(target_os = "linux")]
    {
        let target = if path_buf.is_dir() {
            path_buf.clone()
        } else {
            path_buf
                .parent()
                .map(Path::to_path_buf)
                .unwrap_or_else(|| path_buf.clone())
        };
        Command::new("xdg-open")
            .arg(&target)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .args(["-R", &path_buf.to_string_lossy()])
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "windows")]
    {
        Command::new("explorer")
            .arg("/select,")
            .arg(&path_buf.to_string_lossy().replace('/', "\\"))
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        return Err("Révélation non supportée sur cette plateforme".to_string());
    }

    Ok(())
}

#[tauri::command]
pub fn list_documents(project_path: String) -> Result<Vec<DocumentEntry>, String> {
    let project_root = PathBuf::from(&project_path);
    if !project_root.is_dir() {
        return Err(format!(
            "Le dossier de l'espace n'existe pas : {project_path}"
        ));
    }

    let mut entries = Vec::new();
    collect_documents(&project_root, &project_root, &mut entries)?;
    entries.sort_by(|left, right| left.relative_path.cmp(&right.relative_path));
    Ok(entries)
}

fn open_target_in_os(target: &str) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        Command::new("cmd")
            .args(["/C", "start", "", target])
            .spawn()
            .map_err(|error| error.to_string())?;
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(target)
            .spawn()
            .map_err(|error| error.to_string())?;
    }

    #[cfg(target_os = "linux")]
    {
        Command::new("xdg-open")
            .arg(target)
            .spawn()
            .map_err(|error| error.to_string())?;
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        return Err("Ouverture non supportée sur cette plateforme".to_string());
    }

    Ok(())
}

fn open_path_in_os(path: &Path) -> Result<(), String> {
    open_target_in_os(&path.to_string_lossy())
}

#[tauri::command]
pub fn open_path(path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(&path);
    if !path_buf.exists() {
        return Err(format!("Le chemin n'existe pas : {path}"));
    }

    open_path_in_os(&path_buf)
}

#[tauri::command]
pub fn open_external_url(url: String) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("URL vide".to_string());
    }
    let lower = trimmed.to_ascii_lowercase();
    if !lower.starts_with("http://") && !lower.starts_with("https://") {
        return Err("Seules les URL http(s) sont autorisées".to_string());
    }
    open_target_in_os(trimmed)
}

fn persist_last_project_path(app: &AppHandle, workspace: &WorkspaceInfo) -> Result<(), String> {
    let config = LastProjectConfig {
        project_path: workspace.folder_path.clone(),
        workspace_id: Some(workspace.id.clone()),
    };
    let file_path = last_project_file_path(app)?;
    if let Some(parent) = file_path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let json = serde_json::to_string_pretty(&config).map_err(|error| error.to_string())?;
    fs::write(file_path, json).map_err(|error| error.to_string())?;
    Ok(())
}

fn last_project_file_path(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map(|dir| dir.join(LAST_PROJECT_FILE))
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn restore_last_project_path(
    app: AppHandle,
    state: State<'_, ProjectState>,
) -> Result<Option<WorkspaceInfo>, String> {
    let file_path = last_project_file_path(&app)?;
    if !file_path.is_file() {
        return Ok(None);
    }

    let raw = fs::read_to_string(file_path).map_err(|error| error.to_string())?;
    let config: LastProjectConfig =
        serde_json::from_str(&raw).map_err(|error| error.to_string())?;
    let path = PathBuf::from(&config.project_path);
    if !path.is_dir() {
        return Ok(None);
    }

    Ok(Some(activate_workspace(&app, &state, &path)?))
}

// Compatibilité ascendante pour d'anciens appels front.
#[tauri::command]
pub fn get_workproba_dir(app: AppHandle, project_path: String) -> Result<String, String> {
    if let Some(data_dir) = workspace_store::get_workspace_data_dir_for_folder(&app, &project_path)?
    {
        return Ok(data_dir);
    }

    let path = PathBuf::from(&project_path);
    let workspace = workspace_store::open_or_create_workspace(&app, &path)?;
    Ok(workspace.data_dir)
}

#[tauri::command]
pub fn ensure_workproba_dir(app: AppHandle, project_path: String) -> Result<String, String> {
    get_workproba_dir(app, project_path)
}

// Conservé pour la doc : le dossier métadonnées n'est plus dans le projet utilisateur.
pub const WORKPROBA_METADATA_DIR: &str = WORKPROBA_DIR_NAME;
