use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

const SETTINGS_FILE: &str = "settings.json";
const SETTINGS_VERSION: u32 = 1;

/// Providers LLM reconnus. Miroir de `app.config.ProviderName` côté sidecar.
const KNOWN_PROVIDERS: &[&str] = &[
    "openai_compat",
    "openai",
    "mistral",
    "ollama",
    "vllm",
    "anthropic",
];

/// Une configuration de modèle gérée depuis l'app.
///
/// `api_key` est partagée entre chat et embeddings pour la même entrée
/// (cas courant : une seule clé Mistral sert aux deux).
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct LlmProviderEntry {
    pub id: String,
    pub label: String,
    pub provider: String,
    pub model: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    pub extra_headers: HashMap<String, String>,
    /// Embeddings RAG (optionnel). Si absent, le RAG se désactive ou utilise
    /// le repli sidecar.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub embedding_model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub embedding_base_url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(rename_all = "lowercase")]
pub enum ToolCallViewMode {
    #[default]
    Human,
    Tech,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(rename_all = "lowercase")]
pub enum SettingsMode {
    #[default]
    Guided,
    Advanced,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(rename_all = "lowercase")]
pub enum DensityMode {
    Compact,
    #[default]
    Comfortable,
    Spacious,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub version: u32,
    #[serde(default)]
    pub providers: Vec<LlmProviderEntry>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_chat_provider_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_embedding_provider_id: Option<String>,
    /// Préférence d'affichage des appels d'outil dans le chat.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_call_view: Option<ToolCallViewMode>,
    /// Mode de l'écran de réglages (guidé / avancé).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub settings_mode: Option<SettingsMode>,
    /// Verrouillage des réglages (onboarding / anti-casse).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub settings_locked: Option<bool>,
    /// Densité d'affichage de l'UI.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub density: Option<DensityMode>,
    /// Onboarding validé par l'utilisateur.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub onboarding_done: Option<bool>,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            version: SETTINGS_VERSION,
            providers: Vec::new(),
            active_chat_provider_id: None,
            active_embedding_provider_id: None,
            tool_call_view: None,
            settings_mode: None,
            settings_locked: None,
            density: None,
            onboarding_done: None,
        }
    }
}

fn settings_path(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map(|dir| dir.join(SETTINGS_FILE))
        .map_err(|error| error.to_string())
}

pub fn load_settings(app: &AppHandle) -> Result<AppSettings, String> {
    let path = settings_path(app)?;
    if !path.is_file() {
        return Ok(AppSettings::default());
    }
    let raw = fs::read_to_string(&path).map_err(|error| error.to_string())?;
    if raw.trim().is_empty() {
        return Ok(AppSettings::default());
    }
    let mut settings: AppSettings = serde_json::from_str(&raw).map_err(|error| error.to_string())?;
    // Migration / robustesse : on force la version courante.
    settings.version = SETTINGS_VERSION;
    Ok(settings)
}

pub fn save_settings(app: &AppHandle, settings: &AppSettings) -> Result<(), String> {
    let path = settings_path(app)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let json = serde_json::to_string_pretty(settings).map_err(|error| error.to_string())?;
    fs::write(path, json).map_err(|error| error.to_string())
}

/// Validation légère d'une entrée avant persistance.
pub fn validate_entry(entry: &LlmProviderEntry) -> Result<(), String> {
    if entry.id.trim().is_empty() {
        return Err("Identifiant de provider manquant".to_string());
    }
    if entry.label.trim().is_empty() {
        return Err("Libellé de provider manquant".to_string());
    }
    if !KNOWN_PROVIDERS.contains(&entry.provider.as_str()) {
        return Err(format!("Provider inconnu : {}", entry.provider));
    }
    if entry.model.trim().is_empty() {
        return Err("Modèle manquant".to_string());
    }
    Ok(())
}

#[tauri::command]
pub fn get_app_settings(app: AppHandle) -> Result<AppSettings, String> {
    load_settings(&app)
}

#[tauri::command]
pub fn save_app_settings(app: AppHandle, settings: AppSettings) -> Result<AppSettings, String> {
    for entry in &settings.providers {
        validate_entry(entry)?;
    }
    // Cohérence : les IDs actifs doivent exister dans la liste.
    let ids: Vec<&str> = settings.providers.iter().map(|p| p.id.as_str()).collect();
    let active_chat = if settings
        .active_chat_provider_id
        .as_deref()
        .is_some_and(|id| ids.contains(&id))
    {
        settings.active_chat_provider_id.clone()
    } else {
        None
    };
    let active_embedding = if settings
        .active_embedding_provider_id
        .as_deref()
        .is_some_and(|id| ids.contains(&id))
    {
        settings.active_embedding_provider_id.clone()
    } else {
        None
    };
    let to_persist = AppSettings {
        version: SETTINGS_VERSION,
        providers: settings.providers,
        active_chat_provider_id: active_chat,
        active_embedding_provider_id: active_embedding,
        tool_call_view: settings.tool_call_view,
        settings_mode: settings.settings_mode,
        settings_locked: settings.settings_locked,
        density: settings.density,
        onboarding_done: settings.onboarding_done,
    };
    save_settings(&app, &to_persist)?;
    Ok(to_persist)
}
