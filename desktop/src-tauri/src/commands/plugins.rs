use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

use super::audit::log_audit_event;
use super::settings_store::{load_settings, AppSettings};
use crate::commands::atomic_io::atomic_write;

const PLUGINS_DIR: &str = "plugins";
const REGISTRY_FILE: &str = "registry.json";
const LOCAL_PLUGINS_DIR: &str = "local";
const MANIFEST_FILE: &str = "manifest.json";

/// Manifeste plugin (contrat V2, interface partagée front / sidecar).
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PluginManifest {
    pub id: String,
    pub name: String,
    pub version: String,
    pub description: String,
    pub permissions: Vec<String>,
    pub default_enabled: bool,
    pub ui_slots: Vec<String>,
    pub hooks: Vec<String>,
    pub is_builtin: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum PluginSource {
    Builtin,
    Local,
}

impl PluginSource {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Builtin => "builtin",
            Self::Local => "local",
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PluginInfo {
    pub manifest: PluginManifest,
    pub enabled: bool,
    pub enabled_scoped: bool,
    pub source: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct RegistryEntry {
    id: String,
    enabled: bool,
    source: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PluginRegistry {
    plugins: Vec<RegistryEntry>,
}

fn plugins_root(app_data: &Path) -> PathBuf {
    app_data.join(PLUGINS_DIR)
}

fn registry_path(app_data: &Path) -> PathBuf {
    plugins_root(app_data).join(REGISTRY_FILE)
}

fn plugin_data_dir(app_data: &Path, plugin_id: &str) -> PathBuf {
    plugins_root(app_data).join(plugin_id)
}

fn local_plugins_root(app_data: &Path) -> PathBuf {
    plugins_root(app_data).join(LOCAL_PLUGINS_DIR)
}

fn local_plugin_dir(app_data: &Path, plugin_id: &str) -> PathBuf {
    local_plugins_root(app_data).join(plugin_id)
}

pub fn builtin_manifests() -> Vec<PluginManifest> {
    vec![
        PluginManifest {
            id: "workproba.projet".to_string(),
            name: "plugin.workproba.projet.name".to_string(),
            version: "1.0.0".to_string(),
            description: "plugin.workproba.projet.description".to_string(),
            permissions: vec![
                "space:read".to_string(),
                "files:write".to_string(),
                "agent:tools".to_string(),
                "ui:panels".to_string(),
                "ui:composer".to_string(),
                "settings:section".to_string(),
                "hooks:subscribe".to_string(),
                "storage:namespace".to_string(),
            ],
            default_enabled: false,
            ui_slots: vec![
                "right_panel".to_string(),
                "composer_actions".to_string(),
                "settings".to_string(),
            ],
            hooks: vec![
                "space.opened".to_string(),
                "file.written".to_string(),
                "tool.call_completed".to_string(),
            ],
            is_builtin: true,
        },
        PluginManifest {
            id: "workproba.personas".to_string(),
            name: "plugin.workproba.personas.name".to_string(),
            version: "1.0.0".to_string(),
            description: "plugin.workproba.personas.description".to_string(),
            permissions: vec![
                "agent:tools".to_string(),
                "ui:panels".to_string(),
                "ui:composer".to_string(),
                "settings:section".to_string(),
                "hooks:subscribe".to_string(),
                "storage:namespace".to_string(),
                "core.providers.llm".to_string(),
                "core.memory.search".to_string(),
                "memory:forget".to_string(),
            ],
            default_enabled: true,
            ui_slots: vec![
                "left_panel".to_string(),
                "composer_actions".to_string(),
                "settings".to_string(),
                "side_chat".to_string(),
            ],
            hooks: vec![],
            is_builtin: true,
        },
        PluginManifest {
            id: "workproba.browser".to_string(),
            name: "plugin.workproba.browser.name".to_string(),
            version: "1.0.0".to_string(),
            description: "plugin.workproba.browser.description".to_string(),
            permissions: vec![
                "agent:tools".to_string(),
                "ui:panels".to_string(),
                "hooks:subscribe".to_string(),
                "storage:namespace".to_string(),
                "network:custom".to_string(),
            ],
            default_enabled: false,
            ui_slots: vec!["right_panel".to_string()],
            hooks: vec![],
            is_builtin: true,
        },
        PluginManifest {
            id: "workproba.cloud".to_string(),
            name: "plugin.workproba.cloud.name".to_string(),
            version: "0.1.0".to_string(),
            description: "plugin.workproba.cloud.description".to_string(),
            permissions: vec![
                "storage:namespace".to_string(),
                "project:sync".to_string(),
                "network:improba-cloud".to_string(),
                "ui:panels".to_string(),
                "settings:section".to_string(),
            ],
            default_enabled: false,
            ui_slots: vec!["settings".to_string()],
            hooks: vec![],
            is_builtin: true,
        },
    ]
}

fn is_known_permission(permission: &str) -> bool {
    const KNOWN: &[&str] = &[
        "space:read",
        "files:write",
        "agent:tools",
        "ui:panels",
        "ui:composer",
        "settings:section",
        "hooks:subscribe",
        "storage:namespace",
        "network:improba-cloud",
        "network:custom",
        "network:*",
        "plugin.local",
        "code:execute",
        "core.providers.llm",
        "core.memory.search",
        "memory:forget",
        "project:sync",
    ];

    if KNOWN.contains(&permission) {
        return true;
    }

    permission.starts_with("storage:cross:")
}

fn validate_plugin_id(id: &str) -> Result<(), String> {
    if id.trim().is_empty() {
        return Err("Identifiant plugin manquant".to_string());
    }
    if id.contains('/') || id.contains('\\') {
        return Err(format!("Identifiant plugin invalide : séparateurs interdits : {id}"));
    }
    if id.contains("..") {
        return Err(format!("Identifiant plugin invalide : séquence .. interdite : {id}"));
    }
    let parts: Vec<&str> = id.split('.').collect();
    if parts.len() < 2 {
        return Err(format!(
            "Identifiant plugin invalide (namespace.slug attendu) : {id}"
        ));
    }
    if parts.iter().any(|part| part.is_empty()) {
        return Err(format!("Identifiant plugin invalide : {id}"));
    }
    Ok(())
}

pub fn validate_manifest(manifest: &PluginManifest) -> Result<(), String> {
    validate_plugin_id(&manifest.id)?;
    if manifest.name.trim().is_empty() {
        return Err("Nom du plugin manquant".to_string());
    }
    if manifest.version.trim().is_empty() {
        return Err("Version du plugin manquante".to_string());
    }
    if manifest.description.trim().is_empty() {
        return Err("Description du plugin manquante".to_string());
    }
    for permission in &manifest.permissions {
        if !is_known_permission(permission) {
            return Err(format!("Permission inconnue : {permission}"));
        }
    }
    Ok(())
}

fn is_locked(settings: &AppSettings) -> bool {
    settings.settings_locked.unwrap_or(false)
}

fn local_plugins_allowed(settings: &AppSettings) -> bool {
    if let Some(allowed) = settings.local_plugins_allowed {
        return allowed;
    }
    !is_locked(settings)
}

fn plugin_allowed_by_preset(settings: &AppSettings, plugin_id: &str) -> bool {
    if !is_locked(settings) {
        return true;
    }
    match &settings.plugins_allowed {
        Some(allowed) => allowed.iter().any(|id| id == plugin_id),
        None => true,
    }
}

fn permissions_allowed(settings: &AppSettings, manifest: &PluginManifest) -> Result<(), String> {
    if is_locked(settings) {
        if manifest.permissions.iter().any(|p| p == "code:execute") {
            return Err("Permission code:execute interdite en mode verrouillé".to_string());
        }
        if settings.permissions_network == Some(false)
            && manifest
                .permissions
                .iter()
                .any(|p| p.starts_with("network:"))
        {
            return Err("Permission réseau interdite par le preset".to_string());
        }
        if settings.permissions_network_improba_cloud == Some(false)
            && manifest
                .permissions
                .iter()
                .any(|p| p == "network:improba-cloud")
        {
            return Err("Permission network:improba-cloud interdite par le preset".to_string());
        }
        if settings.permissions_project_sync == Some(false)
            && manifest.permissions.iter().any(|p| p == "project:sync")
        {
            return Err("Permission project:sync interdite par le preset".to_string());
        }
    }
    Ok(())
}

fn can_activate(
    settings: &AppSettings,
    manifest: &PluginManifest,
    source: &PluginSource,
) -> Result<(), String> {
    validate_manifest(manifest)?;
    permissions_allowed(settings, manifest)?;

    if !plugin_allowed_by_preset(settings, &manifest.id) {
        return Err(format!(
            "Plugin non autorisé par le preset : {}",
            manifest.id
        ));
    }

    if *source == PluginSource::Local && !local_plugins_allowed(settings) {
        return Err("Plugins locaux interdits par le preset ou le mode courant".to_string());
    }

    Ok(())
}

fn is_effectively_enabled(
    settings: &AppSettings,
    manifest: &PluginManifest,
    source: &PluginSource,
    enabled: bool,
) -> bool {
    if !enabled {
        return false;
    }
    can_activate(settings, manifest, source).is_ok()
}

fn load_registry(app_data: &Path) -> Result<PluginRegistry, String> {
    let path = registry_path(app_data);
    if !path.is_file() {
        return Ok(PluginRegistry {
            plugins: Vec::new(),
        });
    }
    let raw = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}

fn save_registry(app_data: &Path, registry: &PluginRegistry) -> Result<(), String> {
    let path = registry_path(app_data);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string_pretty(registry).map_err(|e| e.to_string())?;
    atomic_write(&path, &json)
}

fn registry_entry<'a>(registry: &'a PluginRegistry, plugin_id: &str) -> Option<&'a RegistryEntry> {
    registry.plugins.iter().find(|e| e.id == plugin_id)
}

fn upsert_registry_entry(
    registry: &mut PluginRegistry,
    id: String,
    enabled: bool,
    source: &PluginSource,
) {
    if let Some(entry) = registry.plugins.iter_mut().find(|e| e.id == id) {
        entry.enabled = enabled;
        entry.source = source.as_str().to_string();
        return;
    }
    registry.plugins.push(RegistryEntry {
        id,
        enabled,
        source: source.as_str().to_string(),
    });
}

fn remove_registry_entry(registry: &mut PluginRegistry, plugin_id: &str) {
    registry.plugins.retain(|e| e.id != plugin_id);
}

fn read_manifest_file(path: &Path) -> Result<PluginManifest, String> {
    let raw = fs::read_to_string(path).map_err(|e| format!("Manifeste illisible : {e}"))?;
    let manifest: PluginManifest =
        serde_json::from_str(&raw).map_err(|e| format!("Manifeste invalide : {e}"))?;
    validate_manifest(&manifest)?;
    Ok(manifest)
}

fn discover_local_manifests(app_data: &Path) -> Result<Vec<PluginManifest>, String> {
    let root = local_plugins_root(app_data);
    if !root.is_dir() {
        return Ok(Vec::new());
    }

    let mut manifests = Vec::new();
    for entry in fs::read_dir(&root).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if !entry.file_type().map_err(|e| e.to_string())?.is_dir() {
            continue;
        }
        let manifest_path = entry.path().join(MANIFEST_FILE);
        if !manifest_path.is_file() {
            continue;
        }
        manifests.push(read_manifest_file(&manifest_path)?);
    }
    Ok(manifests)
}

fn resolve_enabled(
    registry: &PluginRegistry,
    manifest: &PluginManifest,
    source: &PluginSource,
) -> bool {
    if let Some(entry) = registry_entry(registry, &manifest.id) {
        return entry.enabled;
    }
    manifest.default_enabled && *source == PluginSource::Builtin
}

fn build_plugin_info(
    settings: &AppSettings,
    manifest: PluginManifest,
    source: PluginSource,
    registry: &PluginRegistry,
) -> PluginInfo {
    let enabled = resolve_enabled(registry, &manifest, &source);
    let enabled_scoped = is_effectively_enabled(settings, &manifest, &source, enabled);
    PluginInfo {
        manifest,
        enabled,
        enabled_scoped,
        source: source.as_str().to_string(),
    }
}

pub fn list_plugins_at(app_data: &Path, settings: &AppSettings) -> Result<Vec<PluginInfo>, String> {
    let registry = load_registry(app_data)?;
    let mut infos: Vec<PluginInfo> = builtin_manifests()
        .into_iter()
        .map(|manifest| build_plugin_info(settings, manifest, PluginSource::Builtin, &registry))
        .collect();

    for manifest in discover_local_manifests(app_data)? {
        if infos.iter().any(|info| info.manifest.id == manifest.id) {
            return Err(format!(
                "Conflit d'identifiant plugin (builtin vs local) : {}",
                manifest.id
            ));
        }
        infos.push(build_plugin_info(
            settings,
            manifest,
            PluginSource::Local,
            &registry,
        ));
    }

    infos.sort_by(|a, b| a.manifest.id.cmp(&b.manifest.id));
    Ok(infos)
}

fn find_manifest(
    app_data: &Path,
    plugin_id: &str,
) -> Result<(PluginManifest, PluginSource), String> {
    if let Some(manifest) = builtin_manifests().into_iter().find(|m| m.id == plugin_id) {
        return Ok((manifest, PluginSource::Builtin));
    }

    for manifest in discover_local_manifests(app_data)? {
        if manifest.id == plugin_id {
            return Ok((manifest, PluginSource::Local));
        }
    }

    Err(format!("Plugin inconnu : {plugin_id}"))
}

pub fn activate_plugin_at(
    app_data: &Path,
    settings: &AppSettings,
    plugin_id: &str,
) -> Result<(), String> {
    validate_plugin_id(plugin_id)?;
    let (manifest, source) = find_manifest(app_data, plugin_id)?;
    can_activate(settings, &manifest, &source)?;

    let data_dir = plugin_data_dir(app_data, plugin_id);
    fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

    let mut registry = load_registry(app_data)?;
    upsert_registry_entry(&mut registry, plugin_id.to_string(), true, &source);
    save_registry(app_data, &registry)?;
    let _ = log_audit_event(
        app_data,
        "plugin.activated",
        "user",
        serde_json::json!({"plugin_id": plugin_id}),
    );
    Ok(())
}

pub fn deactivate_plugin_at(app_data: &Path, plugin_id: &str) -> Result<(), String> {
    validate_plugin_id(plugin_id)?;
    let (manifest, source) = find_manifest(app_data, plugin_id)?;
    let mut registry = load_registry(app_data)?;
    upsert_registry_entry(&mut registry, manifest.id, false, &source);
    save_registry(app_data, &registry)?;
    let _ = log_audit_event(
        app_data,
        "plugin.deactivated",
        "user",
        serde_json::json!({"plugin_id": plugin_id}),
    );
    Ok(())
}

pub fn get_plugin_data_dir_at(app_data: &Path, plugin_id: &str) -> Result<String, String> {
    validate_plugin_id(plugin_id)?;
    let dir = plugin_data_dir(app_data, plugin_id);
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.to_string_lossy().to_string())
}

const CLOUD_PLUGIN_ID: &str = "workproba.cloud";
const CLOUD_CONFIG_FILE: &str = "config.json";

pub fn write_cloud_plugin_config(
    app_data: &Path,
    endpoint: Option<&str>,
    org_id: Option<&str>,
) -> Result<(), String> {
    if endpoint.is_none() && org_id.is_none() {
        return Ok(());
    }
    let data_dir = plugin_data_dir(app_data, CLOUD_PLUGIN_ID);
    fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    let config_path = data_dir.join(CLOUD_CONFIG_FILE);
    let mut config: serde_json::Value = if config_path.is_file() {
        let raw = fs::read_to_string(&config_path).unwrap_or_default();
        serde_json::from_str(&raw).unwrap_or_else(|_| serde_json::json!({}))
    } else {
        serde_json::json!({})
    };
    if let Some(url) = endpoint.filter(|value| !value.trim().is_empty()) {
        config["base_url"] = serde_json::Value::String(url.trim().to_string());
    }
    if let Some(org) = org_id.filter(|value| !value.trim().is_empty()) {
        config["org_id"] = serde_json::Value::String(org.trim().to_string());
    }
    let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    atomic_write(&config_path, &json)
}

fn cloud_preset_should_enable(
    settings: &AppSettings,
    preset: &super::preset::EnterprisePreset,
) -> bool {
    let network_improba_cloud = preset
        .permissions_network_improba_cloud
        .or(settings.permissions_network_improba_cloud)
        .unwrap_or(false);
    let project_sync = preset
        .permissions_project_sync
        .or(settings.permissions_project_sync)
        .unwrap_or(false);
    if !network_improba_cloud || !project_sync {
        return false;
    }
    if !is_locked(settings) && !preset.settings_locked {
        return false;
    }
    match &preset.plugins_allowed {
        Some(allowed) => allowed.iter().any(|id| id == CLOUD_PLUGIN_ID),
        None => settings
            .plugins_allowed
            .as_ref()
            .map(|allowed| allowed.iter().any(|id| id == CLOUD_PLUGIN_ID))
            .unwrap_or(true),
    }
}

pub fn apply_preset_cloud_policy(
    app_data: &Path,
    settings: &AppSettings,
    preset: &super::preset::EnterprisePreset,
) {
    let endpoint = preset
        .cloud_endpoint
        .as_deref()
        .or(settings.cloud_endpoint.as_deref());
    let org_id = preset
        .cloud_org_id
        .as_deref()
        .or(settings.cloud_org_id.as_deref());
    let _ = write_cloud_plugin_config(app_data, endpoint, org_id);

    if !preset.settings_locked && !is_locked(settings) {
        return;
    }

    if cloud_preset_should_enable(settings, preset) {
        let _ = activate_plugin_at(app_data, settings, CLOUD_PLUGIN_ID);
        return;
    }

    if preset.permissions_network_improba_cloud == Some(false)
        || preset.permissions_project_sync == Some(false)
    {
        let _ = deactivate_plugin_at(app_data, CLOUD_PLUGIN_ID);
    }
}

fn copy_dir_all(src: &Path, dst: &Path) -> Result<(), String> {
    fs::create_dir_all(dst).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(src).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let file_type = entry.file_type().map_err(|e| e.to_string())?;
        let target = dst.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_all(&entry.path(), &target)?;
        } else {
            fs::copy(entry.path(), &target).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

pub fn install_local_plugin_at(
    app_data: &Path,
    settings: &AppSettings,
    folder_path: &str,
) -> Result<PluginInfo, String> {
    if !local_plugins_allowed(settings) {
        return Err("Plugins locaux interdits par le preset ou le mode courant".to_string());
    }

    let source_dir = Path::new(folder_path);
    if !source_dir.is_dir() {
        return Err(format!("Dossier plugin introuvable : {folder_path}"));
    }

    let manifest_path = source_dir.join(MANIFEST_FILE);
    let mut manifest = read_manifest_file(&manifest_path)?;
    if manifest.is_builtin {
        return Err("Un plugin local ne peut pas être marqué builtin".to_string());
    }

    if builtin_manifests().iter().any(|m| m.id == manifest.id) {
        return Err(format!("Conflit avec un plugin builtin : {}", manifest.id));
    }

    if manifest.permissions.iter().any(|p| p == "plugin.local") {
        return Err("Permission plugin.local réservée au chargeur, pas au manifeste".to_string());
    }

    can_activate(settings, &manifest, &PluginSource::Local)?;

    let dest = local_plugin_dir(app_data, &manifest.id);
    if dest.exists() {
        fs::remove_dir_all(&dest).map_err(|e| e.to_string())?;
    }
    copy_dir_all(source_dir, &dest)?;

    // Relecture depuis la copie installée.
    manifest = read_manifest_file(&dest.join(MANIFEST_FILE))?;

    let mut registry = load_registry(app_data)?;
    let enabled = manifest.default_enabled;
    upsert_registry_entry(
        &mut registry,
        manifest.id.clone(),
        enabled,
        &PluginSource::Local,
    );
    save_registry(app_data, &registry)?;

    if enabled {
        let data_dir = plugin_data_dir(app_data, &manifest.id);
        fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    }

    let registry = load_registry(app_data)?;
    Ok(build_plugin_info(
        settings,
        manifest,
        PluginSource::Local,
        &registry,
    ))
}

pub fn uninstall_local_plugin_at(app_data: &Path, plugin_id: &str) -> Result<(), String> {
    validate_plugin_id(plugin_id)?;
    let (_, source) = find_manifest(app_data, plugin_id)?;
    if source != PluginSource::Local {
        return Err("Seuls les plugins locaux peuvent être désinstallés".to_string());
    }

    let install_dir = local_plugin_dir(app_data, plugin_id);
    if install_dir.is_dir() {
        fs::remove_dir_all(&install_dir).map_err(|e| e.to_string())?;
    }

    let mut registry = load_registry(app_data)?;
    remove_registry_entry(&mut registry, plugin_id);
    save_registry(app_data, &registry)?;
    Ok(())
}

fn app_data_root(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_data_dir().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn list_plugins(app: AppHandle) -> Result<Vec<PluginInfo>, String> {
    let app_data = app_data_root(&app)?;
    let settings = load_settings(&app)?;
    list_plugins_at(&app_data, &settings)
}

#[tauri::command]
pub fn activate_plugin(app: AppHandle, id: String) -> Result<(), String> {
    let app_data = app_data_root(&app)?;
    let settings = load_settings(&app)?;
    activate_plugin_at(&app_data, &settings, &id)
}

#[tauri::command]
pub fn deactivate_plugin(app: AppHandle, id: String) -> Result<(), String> {
    let app_data = app_data_root(&app)?;
    deactivate_plugin_at(&app_data, &id)
}

#[tauri::command]
pub fn get_plugin_data_dir(app: AppHandle, plugin_id: String) -> Result<String, String> {
    let app_data = app_data_root(&app)?;
    get_plugin_data_dir_at(&app_data, &plugin_id)
}

#[tauri::command]
pub fn install_local_plugin(app: AppHandle, folder_path: String) -> Result<PluginInfo, String> {
    let app_data = app_data_root(&app)?;
    let settings = load_settings(&app)?;
    install_local_plugin_at(&app_data, &settings, &folder_path)
}

#[tauri::command]
pub fn uninstall_local_plugin(app: AppHandle, id: String) -> Result<(), String> {
    let app_data = app_data_root(&app)?;
    uninstall_local_plugin_at(&app_data, &id)
}

#[cfg(test)]
mod plugins_tests {
    use super::*;
    use crate::commands::settings_store::AppSettings;
    use uuid::Uuid;

    fn temp_app_data() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("wp_plugins_test_{}", Uuid::new_v4()));
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    fn sample_local_manifest(id: &str) -> PluginManifest {
        PluginManifest {
            id: id.to_string(),
            name: "plugin.test.name".to_string(),
            version: "0.1.0".to_string(),
            description: "plugin.test.description".to_string(),
            permissions: vec!["storage:namespace".to_string()],
            default_enabled: false,
            ui_slots: vec!["settings".to_string()],
            hooks: vec![],
            is_builtin: false,
        }
    }

    fn write_local_plugin_folder(base: &Path, manifest: &PluginManifest) -> PathBuf {
        let folder = base.join("source_plugin");
        fs::create_dir_all(&folder).expect("mkdir source");
        let json = serde_json::to_string_pretty(manifest).expect("serialize manifest");
        fs::write(folder.join(MANIFEST_FILE), json).expect("write manifest");
        folder
    }

    #[test]
    fn builtin_manifest_permissions_projet_and_cloud() {
        let manifests = builtin_manifests();
        let projet = manifests
            .iter()
            .find(|m| m.id == "workproba.projet")
            .expect("projet");
        assert!(
            !projet
                .permissions
                .contains(&"storage:cross:workproba.projet".to_string()),
            "projet must not grant cross-self storage permission"
        );

        let cloud = manifests
            .iter()
            .find(|m| m.id == "workproba.cloud")
            .expect("cloud");
        assert!(
            cloud
                .permissions
                .contains(&"network:improba-cloud".to_string()),
            "cloud must use network:improba-cloud"
        );
        assert!(
            cloud.permissions.contains(&"project:sync".to_string()),
            "cloud must use project:sync"
        );
        assert!(
            !cloud
                .permissions
                .contains(&"storage:cross:workproba.projet".to_string()),
            "cloud must not use storage:cross:workproba.projet"
        );
        assert!(
            !cloud.permissions.contains(&"network:custom".to_string()),
            "cloud must not use network:custom"
        );
    }

    #[test]
    fn cloud_activation_blocked_when_network_improba_cloud_preset_false() {
        let app_data = temp_app_data();
        let settings = AppSettings {
            settings_locked: Some(true),
            permissions_project_sync: Some(true),
            permissions_network_improba_cloud: Some(false),
            ..AppSettings::default()
        };

        let err = activate_plugin_at(&app_data, &settings, "workproba.cloud")
            .expect_err("cloud blocked by network_improba_cloud preset");
        assert!(err.contains("network:improba-cloud"));
    }

    #[test]
    fn cloud_activation_blocked_when_project_sync_preset_false() {
        let app_data = temp_app_data();
        let settings = AppSettings {
            settings_locked: Some(true),
            permissions_project_sync: Some(false),
            ..AppSettings::default()
        };

        let err = activate_plugin_at(&app_data, &settings, "workproba.cloud")
            .expect_err("cloud blocked by project_sync preset");
        assert!(err.contains("project:sync"));
    }

    #[test]
    fn builtin_manifests_include_expected_plugins() {
        let manifests = builtin_manifests();
        assert_eq!(manifests.len(), 4);
        let ids: Vec<&str> = manifests.iter().map(|m| m.id.as_str()).collect();
        assert!(ids.contains(&"workproba.projet"));
        assert!(ids.contains(&"workproba.personas"));
        assert!(ids.contains(&"workproba.browser"));
        assert!(ids.contains(&"workproba.cloud"));

        let personas = manifests
            .iter()
            .find(|m| m.id == "workproba.personas")
            .expect("personas");
        assert!(personas.default_enabled);
        assert!(personas.is_builtin);
        assert!(personas.ui_slots.contains(&"side_chat".to_string()));
    }

    #[test]
    fn registry_roundtrip() {
        let app_data = temp_app_data();
        let registry = PluginRegistry {
            plugins: vec![RegistryEntry {
                id: "workproba.projet".to_string(),
                enabled: true,
                source: "builtin".to_string(),
            }],
        };
        save_registry(&app_data, &registry).expect("save");
        let loaded = load_registry(&app_data).expect("load");
        assert_eq!(loaded.plugins, registry.plugins);
    }

    #[test]
    fn list_plugins_merges_builtin_defaults() {
        let app_data = temp_app_data();
        let settings = AppSettings::default();
        let plugins = list_plugins_at(&app_data, &settings).expect("list");
        assert_eq!(plugins.len(), 4);

        let personas = plugins
            .iter()
            .find(|p| p.manifest.id == "workproba.personas")
            .expect("personas");
        assert!(personas.enabled);
        assert!(personas.enabled_scoped);

        let projet = plugins
            .iter()
            .find(|p| p.manifest.id == "workproba.projet")
            .expect("projet");
        assert!(!projet.enabled);
    }

    #[test]
    fn activate_and_deactivate_plugin() {
        let app_data = temp_app_data();
        let settings = AppSettings::default();

        activate_plugin_at(&app_data, &settings, "workproba.projet").expect("activate");
        let data_dir = plugin_data_dir(&app_data, "workproba.projet");
        assert!(data_dir.is_dir());

        let plugins = list_plugins_at(&app_data, &settings).expect("list");
        let projet = plugins
            .iter()
            .find(|p| p.manifest.id == "workproba.projet")
            .expect("projet");
        assert!(projet.enabled);
        assert!(projet.enabled_scoped);

        deactivate_plugin_at(&app_data, "workproba.projet").expect("deactivate");
        let plugins = list_plugins_at(&app_data, &settings).expect("list after deactivate");
        let projet = plugins
            .iter()
            .find(|p| p.manifest.id == "workproba.projet")
            .expect("projet");
        assert!(!projet.enabled);
        assert!(!projet.enabled_scoped);
        assert!(data_dir.is_dir(), "data dir conservé après désactivation");
    }

    #[test]
    fn get_plugin_data_dir_creates_directory() {
        let app_data = temp_app_data();
        let path = get_plugin_data_dir_at(&app_data, "workproba.personas").expect("dir");
        assert!(Path::new(&path).is_dir());
        assert!(path.contains("plugins/workproba.personas"));
    }

    #[test]
    fn install_local_plugin_refused_when_locked() {
        let app_data = temp_app_data();
        let source_base = temp_app_data();
        let manifest = sample_local_manifest("acme.hello");
        let folder = write_local_plugin_folder(&source_base, &manifest);

        let settings = AppSettings {
            settings_locked: Some(true),
            local_plugins_allowed: Some(false),
            ..AppSettings::default()
        };

        let err = install_local_plugin_at(&app_data, &settings, folder.to_str().unwrap())
            .expect_err("should refuse");
        assert!(err.contains("interdits"));
    }

    #[test]
    fn install_local_plugin_when_not_locked() {
        let app_data = temp_app_data();
        let source_base = temp_app_data();
        let manifest = sample_local_manifest("acme.hello");
        let folder = write_local_plugin_folder(&source_base, &manifest);

        let settings = AppSettings::default();

        let info = install_local_plugin_at(&app_data, &settings, folder.to_str().unwrap())
            .expect("install");
        assert_eq!(info.manifest.id, "acme.hello");
        assert_eq!(info.source, "local");
        assert!(local_plugin_dir(&app_data, "acme.hello").is_dir());
    }

    #[test]
    fn validate_plugin_id_rejects_path_traversal() {
        assert!(validate_plugin_id("acme.hello").is_ok());
        assert!(validate_plugin_id("../escape").is_err());
        assert!(validate_plugin_id("acme/evil").is_err());
        assert!(validate_plugin_id("acme\\evil").is_err());
        assert!(validate_plugin_id("").is_err());
        assert!(validate_plugin_id("single").is_err());
    }

    #[test]
    fn permission_validation_rejects_unknown_permission() {
        let manifest = PluginManifest {
            permissions: vec!["unknown:permission".to_string()],
            ..sample_local_manifest("acme.bad")
        };
        let err = validate_manifest(&manifest).expect_err("unknown permission");
        assert!(err.contains("inconnue"));
    }

    #[test]
    fn activate_browser_blocked_when_network_false_in_locked_mode() {
        let app_data = temp_app_data();
        let settings = AppSettings {
            settings_locked: Some(true),
            plugins_allowed: Some(vec![
                "workproba.personas".to_string(),
                "workproba.browser".to_string(),
            ]),
            permissions_network: Some(false),
            ..AppSettings::default()
        };

        let err = activate_plugin_at(&app_data, &settings, "workproba.browser")
            .expect_err("browser blocked by network preset");
        assert!(err.contains("réseau"));

        let plugins = list_plugins_at(&app_data, &settings).expect("list");
        let browser = plugins
            .iter()
            .find(|p| p.manifest.id == "workproba.browser")
            .expect("browser");
        assert!(!browser.enabled_scoped);
    }

    #[test]
    fn activate_blocked_by_plugins_allowed_in_locked_mode() {
        let app_data = temp_app_data();
        let settings = AppSettings {
            settings_locked: Some(true),
            plugins_allowed: Some(vec!["workproba.personas".to_string()]),
            ..AppSettings::default()
        };

        let err = activate_plugin_at(&app_data, &settings, "workproba.browser")
            .expect_err("browser blocked");
        assert!(err.contains("preset"));

        let plugins = list_plugins_at(&app_data, &settings).expect("list");
        let browser = plugins
            .iter()
            .find(|p| p.manifest.id == "workproba.browser")
            .expect("browser");
        assert!(!browser.enabled_scoped);
    }

    #[test]
    fn code_execute_blocked_in_locked_mode() {
        let app_data = temp_app_data();
        let source_base = temp_app_data();
        let mut manifest = sample_local_manifest("acme.danger");
        manifest.permissions.push("code:execute".to_string());
        let folder = write_local_plugin_folder(&source_base, &manifest);

        let settings = AppSettings {
            settings_locked: Some(true),
            local_plugins_allowed: Some(true),
            ..AppSettings::default()
        };

        let err = install_local_plugin_at(&app_data, &settings, folder.to_str().unwrap())
            .expect_err("code execute blocked");
        assert!(err.contains("code:execute"));
    }
}
