use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

use super::audit::log_audit_event;
use super::settings_store::AppSettings;

const PRESETS_DIR: &str = "presets";
const ENTERPRISE_PRESET_FILE: &str = "enterprise.json";

#[derive(Debug, Serialize, Deserialize, Clone, Default, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct EnterprisePreset {
    #[serde(default)]
    pub settings_locked: bool,
    #[serde(default)]
    pub locale_locked: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locale: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub plugins_allowed: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub local_plugins_allowed: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub permissions_network: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub permissions_project_sync: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code_execute: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audit_retention_days: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audit_enabled: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_sets_locked: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub allowed_provider_set_ids: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct RawPlugins {
    #[serde(default)]
    allowed: Option<Vec<String>>,
    #[serde(default, rename = "local_plugins")]
    local_plugins: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct RawPermissions {
    #[serde(default)]
    network: Option<bool>,
    #[serde(default, rename = "code_execute")]
    code_execute: Option<bool>,
    #[serde(default, rename = "project_sync")]
    project_sync: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct RawUi {
    #[serde(default)]
    locale: Option<String>,
    #[serde(default, rename = "locale_locked")]
    locale_locked: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct RawAudit {
    #[serde(default)]
    enabled: Option<bool>,
    #[serde(default, rename = "retention_days")]
    retention_days: Option<u32>,
}

#[derive(Debug, Deserialize)]
struct RawProviderSet {
    #[serde(default)]
    id: Option<String>,
    #[serde(default)]
    locked: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct RawEnterprisePreset {
    #[serde(default)]
    mode: Option<String>,
    #[serde(default)]
    plugins: Option<RawPlugins>,
    #[serde(default)]
    permissions: Option<RawPermissions>,
    #[serde(default)]
    ui: Option<RawUi>,
    #[serde(default)]
    audit: Option<RawAudit>,
    #[serde(default)]
    provider_set: Option<RawProviderSet>,
    #[serde(flatten)]
    flat: EnterprisePreset,
}

fn presets_dir(app_data: &Path) -> PathBuf {
    app_data.join(PRESETS_DIR)
}

pub fn enterprise_preset_path(app_data: &Path) -> PathBuf {
    presets_dir(app_data).join(ENTERPRISE_PRESET_FILE)
}

pub fn parse_enterprise_preset(raw: &str) -> Result<EnterprisePreset, String> {
    if raw.trim().is_empty() {
        return Err("Preset vide".to_string());
    }
    let nested: RawEnterprisePreset =
        serde_json::from_str(raw).map_err(|error| error.to_string())?;
    let mut preset = nested.flat;
    if nested.mode.as_deref() == Some("locked") {
        preset.settings_locked = true;
    }
    if let Some(plugins) = nested.plugins {
        if preset.plugins_allowed.is_none() {
            preset.plugins_allowed = plugins.allowed;
        }
        if preset.local_plugins_allowed.is_none() {
            preset.local_plugins_allowed = plugins.local_plugins;
        }
    }
    if let Some(permissions) = nested.permissions {
        if preset.permissions_network.is_none() {
            preset.permissions_network = permissions.network;
        }
        if preset.code_execute.is_none() {
            preset.code_execute = permissions.code_execute;
        }
        if preset.permissions_project_sync.is_none() {
            preset.permissions_project_sync = permissions.project_sync;
        }
    }
    if let Some(ui) = nested.ui {
        if preset.locale.is_none() {
            preset.locale = ui.locale;
        }
        if let Some(locked) = ui.locale_locked {
            preset.locale_locked = locked;
        }
    }
    if let Some(audit) = nested.audit {
        if preset.audit_enabled.is_none() {
            preset.audit_enabled = audit.enabled;
        }
        if preset.audit_retention_days.is_none() {
            preset.audit_retention_days = audit.retention_days;
        }
    }
    if let Some(provider_set) = nested.provider_set {
        if preset.provider_sets_locked.is_none() {
            preset.provider_sets_locked = provider_set.locked;
        }
        if preset.allowed_provider_set_ids.is_none() {
            preset.allowed_provider_set_ids = provider_set.id.map(|id| vec![id]);
        }
    }
    Ok(preset)
}

pub fn load_enterprise_preset_at(app_data: &Path) -> Option<EnterprisePreset> {
    let path = enterprise_preset_path(app_data);
    if !path.is_file() {
        return None;
    }
    let raw = fs::read_to_string(&path).ok()?;
    parse_enterprise_preset(&raw).ok()
}

pub fn apply_preset_to_settings(settings: &mut AppSettings, preset: &EnterprisePreset) {
    if preset.settings_locked {
        settings.settings_locked = Some(true);
    }
    if let Some(locale) = &preset.locale {
        settings.locale = Some(locale.clone());
    }
    if preset.locale_locked {
        settings.locale_locked = Some(true);
    }
    if let Some(allowed) = &preset.plugins_allowed {
        settings.plugins_allowed = Some(allowed.clone());
    }
    if let Some(local) = preset.local_plugins_allowed {
        settings.local_plugins_allowed = Some(local);
    }
    if let Some(network) = preset.permissions_network {
        settings.permissions_network = Some(network);
    }
    if let Some(project_sync) = preset.permissions_project_sync {
        settings.permissions_project_sync = Some(project_sync);
    }
    if let Some(code_execute) = preset.code_execute {
        settings.code_execute = Some(code_execute);
    }
    if let Some(retention) = preset.audit_retention_days {
        settings.audit_retention_days = Some(retention);
    }
    if let Some(enabled) = preset.audit_enabled {
        settings.audit_enabled = Some(enabled);
    }
    if let Some(locked) = preset.provider_sets_locked {
        settings.provider_sets_locked = Some(locked);
    }
    if let Some(ids) = &preset.allowed_provider_set_ids {
        settings.allowed_provider_set_ids = Some(ids.clone());
    }
}

pub fn apply_enterprise_preset(app_data: &Path, settings: &mut AppSettings) {
    let Some(preset) = load_enterprise_preset_at(app_data) else {
        return;
    };
    apply_preset_to_settings(settings, &preset);
    let preset_path = enterprise_preset_path(app_data);
    let _ = log_audit_event(
        app_data,
        "preset.applied",
        "system",
        serde_json::json!({
            "preset_path": preset_path.to_string_lossy(),
        }),
    );
}

fn app_data_root(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_data_dir().map_err(|error| error.to_string())
}

#[tauri::command]
pub fn get_enterprise_preset(app: AppHandle) -> Result<Option<EnterprisePreset>, String> {
    let app_data = app_data_root(&app)?;
    Ok(load_enterprise_preset_at(&app_data))
}

#[tauri::command]
pub fn is_preset_active(app: AppHandle) -> Result<bool, String> {
    let app_data = app_data_root(&app)?;
    Ok(load_enterprise_preset_at(&app_data).is_some())
}

#[cfg(test)]
mod preset_tests {
    use super::*;
    use uuid::Uuid;

    fn temp_app_data() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("wp_preset_test_{}", Uuid::new_v4()));
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    #[test]
    fn parse_nested_enterprise_preset() {
        let raw = r#"{
            "preset_id": "improba-eti-rh-2026",
            "mode": "locked",
            "plugins": {
                "allowed": ["workproba.projet", "workproba.personas"],
                "local_plugins": false
            },
            "permissions": {
                "network": false,
                "code_execute": false,
                "project_sync": true
            },
            "ui": {
                "locale": "fr",
                "locale_locked": true
            },
            "audit": {
                "enabled": true,
                "retention_days": 90
            },
            "provider_set": {
                "id": "mistral-eti",
                "locked": true
            }
        }"#;
        let preset = parse_enterprise_preset(raw).expect("parse");
        assert!(preset.settings_locked);
        assert_eq!(preset.locale.as_deref(), Some("fr"));
        assert!(preset.locale_locked);
        assert_eq!(preset.plugins_allowed.as_ref().map(|v| v.len()), Some(2));
        assert_eq!(preset.local_plugins_allowed, Some(false));
        assert_eq!(preset.permissions_network, Some(false));
        assert_eq!(preset.permissions_project_sync, Some(true));
        assert_eq!(preset.code_execute, Some(false));
        assert_eq!(preset.audit_retention_days, Some(90));
        assert_eq!(preset.audit_enabled, Some(true));
        assert_eq!(preset.provider_sets_locked, Some(true));
    }

    #[test]
    fn apply_preset_merges_into_settings() {
        let mut settings = AppSettings::default();
        let preset = EnterprisePreset {
            settings_locked: true,
            locale: Some("fr".to_string()),
            locale_locked: true,
            plugins_allowed: Some(vec!["workproba.projet".to_string()]),
            local_plugins_allowed: Some(false),
            permissions_network: Some(false),
            permissions_project_sync: Some(false),
            code_execute: Some(false),
            audit_retention_days: Some(30),
            audit_enabled: Some(true),
            ..EnterprisePreset::default()
        };
        apply_preset_to_settings(&mut settings, &preset);
        assert_eq!(settings.settings_locked, Some(true));
        assert_eq!(settings.permissions_network, Some(false));
        assert_eq!(settings.permissions_project_sync, Some(false));
        assert_eq!(settings.audit_retention_days, Some(30));
    }

    #[test]
    fn load_enterprise_preset_from_file() {
        let app_data = temp_app_data();
        let presets = presets_dir(&app_data);
        fs::create_dir_all(&presets).expect("mkdir presets");
        fs::write(
            enterprise_preset_path(&app_data),
            r#"{"mode":"locked","permissions":{"network":false}}"#,
        )
        .expect("write preset");
        let preset = load_enterprise_preset_at(&app_data).expect("load");
        assert!(preset.settings_locked);
        assert_eq!(preset.permissions_network, Some(false));
    }
}
