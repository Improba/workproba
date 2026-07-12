use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

use crate::commands::atomic_io::atomic_write;

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

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSetChatEntry {
    pub provider: String,
    pub model: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key_ref: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reasoning: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSetEmbeddingsEntry {
    pub provider: String,
    pub model: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key_ref: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSetOcrEntry {
    pub provider: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mode: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSetVisionEntry {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mode: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSetCapabilitiesEntry {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reasoning: Option<String>,
    #[serde(default)]
    pub vision: bool,
    #[serde(default = "default_tools_true")]
    pub tools: bool,
}

fn default_tools_true() -> bool {
    true
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSetEntry {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub badges: Vec<String>,
    pub chat: ProviderSetChatEntry,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub embeddings: Option<ProviderSetEmbeddingsEntry>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ocr: Option<ProviderSetOcrEntry>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub vision: Option<ProviderSetVisionEntry>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub capabilities: Option<ProviderSetCapabilitiesEntry>,
    #[serde(default)]
    pub is_default: bool,
    #[serde(default)]
    pub is_builtin: bool,
}

pub const MISTRAL_BUILTIN_SET_ID: &str = "mistral-default";
pub const OLLAMA_BUILTIN_SET_ID: &str = "ollama-local";

pub fn builtin_provider_sets() -> Vec<ProviderSetEntry> {
    vec![
        ProviderSetEntry {
            id: MISTRAL_BUILTIN_SET_ID.to_string(),
            name: "Mistral".to_string(),
            description: "Cloud Improba, tout-intégré. Chat, vision, OCR, embeddings.".to_string(),
            badges: vec!["Cloud Improba".to_string(), "Recommandé".to_string()],
            chat: ProviderSetChatEntry {
                provider: "mistral".to_string(),
                model: "mistral-small-latest".to_string(),
                api_key_ref: Some("secrets/mistral".to_string()),
                api_key: None,
                base_url: Some("https://api.mistral.ai/v1".to_string()),
                reasoning: Some("auto".to_string()),
            },
            embeddings: Some(ProviderSetEmbeddingsEntry {
                provider: "mistral".to_string(),
                model: "mistral-embed".to_string(),
                api_key_ref: Some("secrets/mistral".to_string()),
                api_key: None,
                base_url: Some("https://api.mistral.ai/v1".to_string()),
            }),
            ocr: Some(ProviderSetOcrEntry {
                provider: "mistral".to_string(),
                mode: Some("auto".to_string()),
            }),
            vision: Some(ProviderSetVisionEntry {
                mode: Some("chat".to_string()),
            }),
            capabilities: Some(ProviderSetCapabilitiesEntry {
                reasoning: Some("medium".to_string()),
                vision: true,
                tools: true,
            }),
            is_default: true,
            is_builtin: true,
        },
        ProviderSetEntry {
            id: OLLAMA_BUILTIN_SET_ID.to_string(),
            name: "Ollama local".to_string(),
            description: "100 % local. Chat et embeddings sur votre machine.".to_string(),
            badges: vec!["100 % local".to_string()],
            chat: ProviderSetChatEntry {
                provider: "ollama".to_string(),
                model: "llama3.2".to_string(),
                api_key_ref: None,
                api_key: None,
                base_url: Some("http://127.0.0.1:11434/v1".to_string()),
                reasoning: Some("auto".to_string()),
            },
            embeddings: Some(ProviderSetEmbeddingsEntry {
                provider: "ollama".to_string(),
                model: "nomic-embed-text".to_string(),
                api_key_ref: None,
                api_key: None,
                base_url: Some("http://127.0.0.1:11434/v1".to_string()),
            }),
            ocr: None,
            vision: Some(ProviderSetVisionEntry {
                mode: Some("chat".to_string()),
            }),
            capabilities: Some(ProviderSetCapabilitiesEntry {
                reasoning: Some("low".to_string()),
                vision: false,
                tools: true,
            }),
            is_default: false,
            is_builtin: true,
        },
    ]
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(rename_all = "lowercase")]
pub enum ToolCallViewMode {
    #[default]
    Human,
    Tech,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default, PartialEq, Eq)]
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
    /// Provider sets unifiés (chat + embeddings + OCR + vision).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sets: Option<Vec<ProviderSetEntry>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_set_id: Option<String>,
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
    /// Langue de l'interface (fr / en). Absent = défaut côté front.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locale: Option<String>,
    /// Langue imposée par preset : le toggle est masqué côté front.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locale_locked: Option<bool>,
    /// Nom affiché dans l'interface (onboarding profil).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_name: Option<String>,
    /// Organisation affichée dans l'interface (onboarding profil).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_org: Option<String>,
    /// Profil nom/org renseigné au premier lancement.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub profile_onboarding_done: Option<bool>,
    /// Liste blanche de plugins autorisés (preset verrouillé).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub plugins_allowed: Option<Vec<String>>,
    /// Autorise les plugins locaux (preset verrouillé). Absent = défaut selon mode.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub local_plugins_allowed: Option<bool>,
    /// Autorise les permissions réseau (preset verrouillé). `Some(false)` bloque network:*.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub permissions_network: Option<bool>,
    /// Autorise l'exécution de code (preset verrouillé).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code_execute: Option<bool>,
    /// Rétention du journal d'audit (jours).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audit_retention_days: Option<u32>,
    /// Journal d'audit activé.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audit_enabled: Option<bool>,
    /// Sets provider verrouillés par preset.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_sets_locked: Option<bool>,
    /// Identifiants de sets autorisés par preset.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub allowed_provider_set_ids: Option<Vec<String>>,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            version: SETTINGS_VERSION,
            providers: Vec::new(),
            active_chat_provider_id: None,
            active_embedding_provider_id: None,
            sets: None,
            active_set_id: None,
            tool_call_view: None,
            settings_mode: None,
            settings_locked: None,
            density: None,
            onboarding_done: None,
            locale: None,
            locale_locked: None,
            user_name: None,
            user_org: None,
            profile_onboarding_done: None,
            plugins_allowed: None,
            local_plugins_allowed: None,
            permissions_network: None,
            code_execute: None,
            audit_retention_days: None,
            audit_enabled: None,
            provider_sets_locked: None,
            allowed_provider_set_ids: None,
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
    let app_data = path
        .parent()
        .ok_or_else(|| "Répertoire app_data introuvable".to_string())?;
    if !path.is_file() {
        let mut settings = AppSettings::default();
        super::preset::apply_enterprise_preset(app_data, &mut settings);
        return Ok(settings);
    }
    let raw = fs::read_to_string(&path).map_err(|error| error.to_string())?;
    if raw.trim().is_empty() {
        let mut settings = AppSettings::default();
        super::preset::apply_enterprise_preset(app_data, &mut settings);
        return Ok(settings);
    }
    let mut settings: AppSettings = serde_json::from_str(&raw).map_err(|error| error.to_string())?;
    // Migration / robustesse : on force la version courante.
    settings.version = SETTINGS_VERSION;
    migrate_provider_sets(&mut settings);
    super::preset::apply_enterprise_preset(app_data, &mut settings);
    Ok(settings)
}

/// Migre les anciens `providers[]` vers un set unique « Migré » si `sets` est absent.
fn migrate_provider_sets(settings: &mut AppSettings) {
    if settings.sets.is_some() {
        return;
    }
    if settings.providers.is_empty() {
        return;
    }

    let chat_id = settings.active_chat_provider_id.as_deref();
    let embed_id = settings
        .active_embedding_provider_id
        .as_deref()
        .or(chat_id);

    let chat_entry = chat_id
        .and_then(|id| settings.providers.iter().find(|p| p.id == id))
        .or_else(|| settings.providers.first());

    let embed_entry = embed_id
        .and_then(|id| settings.providers.iter().find(|p| p.id == id))
        .or_else(|| chat_entry);

    let Some(chat) = chat_entry else {
        return;
    };

    let migrated_id = format!("migrated-{}", chat.id);
    let embeddings = embed_entry.and_then(|entry| {
        entry.embedding_model.as_ref().map(|model| ProviderSetEmbeddingsEntry {
            provider: entry.provider.clone(),
            model: model.clone(),
            api_key_ref: None,
            api_key: entry.api_key.clone(),
            base_url: entry
                .embedding_base_url
                .clone()
                .or_else(|| entry.base_url.clone()),
        })
    });

    let migrated = ProviderSetEntry {
        id: migrated_id.clone(),
        name: "Migré".to_string(),
        description: format!(
            "Configuration migrée depuis l'ancien provider « {} ».",
            chat.label
        ),
        badges: vec![],
        chat: ProviderSetChatEntry {
            provider: chat.provider.clone(),
            model: chat.model.clone(),
            api_key_ref: None,
            api_key: chat.api_key.clone(),
            base_url: chat.base_url.clone(),
            reasoning: Some("auto".to_string()),
        },
        embeddings,
        ocr: None,
        vision: Some(ProviderSetVisionEntry {
            mode: Some("none".to_string()),
        }),
        capabilities: Some(ProviderSetCapabilitiesEntry {
            reasoning: Some("medium".to_string()),
            vision: false,
            tools: true,
        }),
        is_default: true,
        is_builtin: false,
    };

    settings.sets = Some(vec![migrated]);
    settings.active_set_id = Some(migrated_id);
}

pub fn save_settings(app: &AppHandle, settings: &AppSettings) -> Result<(), String> {
    let path = settings_path(app)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let json = serde_json::to_string_pretty(settings).map_err(|error| error.to_string())?;
    atomic_write(&path, &json)
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

#[cfg(test)]
mod settings_tests {
    use super::*;

    #[test]
    fn default_settings_include_optional_locale() {
        let settings = AppSettings::default();
        assert!(settings.locale.is_none());
    }

    #[test]
    fn settings_deserialize_without_locale_field() {
        let raw = r#"{"version":1,"providers":[]}"#;
        let settings: AppSettings = serde_json::from_str(raw).expect("deserialize");
        assert!(settings.locale.is_none());
    }

    #[test]
    fn settings_deserialize_without_locale_locked_field() {
        let raw = r#"{"version":1,"providers":[],"locale":"fr"}"#;
        let settings: AppSettings = serde_json::from_str(raw).expect("deserialize");
        assert!(settings.locale_locked.is_none());
    }

    #[test]
    fn settings_roundtrip_locale_locked() {
        let settings = AppSettings {
            version: SETTINGS_VERSION,
            providers: Vec::new(),
            active_chat_provider_id: None,
            active_embedding_provider_id: None,
            sets: None,
            active_set_id: None,
            tool_call_view: None,
            settings_mode: None,
            settings_locked: None,
            density: None,
            onboarding_done: None,
            locale: Some("fr".to_string()),
            locale_locked: Some(true),
            user_name: None,
            user_org: None,
            profile_onboarding_done: None,
            plugins_allowed: None,
            local_plugins_allowed: None,
            permissions_network: None,
            code_execute: None,
            audit_retention_days: None,
            audit_enabled: None,
            provider_sets_locked: None,
            allowed_provider_set_ids: None,
        };
        let json = serde_json::to_string(&settings).expect("serialize");
        let parsed: AppSettings = serde_json::from_str(&json).expect("deserialize");
        assert_eq!(parsed.locale.as_deref(), Some("fr"));
        assert_eq!(parsed.locale_locked, Some(true));
    }

    #[test]
    fn migrate_providers_to_single_set_preserves_api_keys() {
        let mut settings = AppSettings {
            version: SETTINGS_VERSION,
            providers: vec![LlmProviderEntry {
                id: "p1".to_string(),
                label: "Mon Mistral".to_string(),
                provider: "mistral".to_string(),
                model: "mistral-small-latest".to_string(),
                base_url: Some("https://api.mistral.ai/v1".to_string()),
                api_key: Some("secret-key".to_string()),
                temperature: None,
                max_tokens: None,
                extra_headers: HashMap::new(),
                embedding_model: Some("mistral-embed".to_string()),
                embedding_base_url: None,
            }],
            active_chat_provider_id: Some("p1".to_string()),
            active_embedding_provider_id: Some("p1".to_string()),
            ..AppSettings::default()
        };
        migrate_provider_sets(&mut settings);
        let sets = settings.sets.expect("sets migrated");
        assert_eq!(sets.len(), 1);
        assert_eq!(sets[0].name, "Migré");
        assert_eq!(sets[0].chat.api_key.as_deref(), Some("secret-key"));
        assert_eq!(
            sets[0].embeddings.as_ref().map(|e| e.model.as_str()),
            Some("mistral-embed")
        );
        assert_eq!(settings.active_set_id.as_deref(), Some("migrated-p1"));
    }

    #[test]
    fn migrate_skips_when_sets_already_present() {
        let existing = builtin_provider_sets();
        let mut settings = AppSettings {
            version: SETTINGS_VERSION,
            providers: vec![LlmProviderEntry {
                id: "p1".to_string(),
                label: "X".to_string(),
                provider: "mistral".to_string(),
                model: "m".to_string(),
                base_url: None,
                api_key: None,
                temperature: None,
                max_tokens: None,
                extra_headers: HashMap::new(),
                embedding_model: None,
                embedding_base_url: None,
            }],
            sets: Some(existing.clone()),
            active_set_id: Some(MISTRAL_BUILTIN_SET_ID.to_string()),
            ..AppSettings::default()
        };
        migrate_provider_sets(&mut settings);
        assert_eq!(settings.sets.as_ref().map(|s| s.len()), Some(existing.len()));
    }

    #[test]
    fn settings_deserialize_without_plugins_allowed_field() {
        let raw = r#"{"version":1,"providers":[]}"#;
        let settings: AppSettings = serde_json::from_str(raw).expect("deserialize");
        assert!(settings.plugins_allowed.is_none());
        assert!(settings.local_plugins_allowed.is_none());
    }

    #[test]
    fn builtin_sets_include_mistral_default() {
        let sets = builtin_provider_sets();
        assert_eq!(sets.len(), 2);
        let mistral = &sets[0];
        assert_eq!(mistral.id, MISTRAL_BUILTIN_SET_ID);
        assert!(mistral.is_default);
        assert!(mistral.is_builtin);
    }
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
    let sets = settings.sets;
    let active_set_id = validate_active_set_id(&sets, settings.active_set_id);
    let to_persist = AppSettings {
        version: SETTINGS_VERSION,
        providers: settings.providers,
        active_chat_provider_id: active_chat,
        active_embedding_provider_id: active_embedding,
        sets,
        active_set_id,
        tool_call_view: settings.tool_call_view,
        settings_mode: settings.settings_mode,
        settings_locked: settings.settings_locked,
        density: settings.density,
        onboarding_done: settings.onboarding_done,
        locale: settings.locale,
        locale_locked: settings.locale_locked,
        user_name: settings.user_name,
        user_org: settings.user_org,
        profile_onboarding_done: settings.profile_onboarding_done,
        plugins_allowed: settings.plugins_allowed,
        local_plugins_allowed: settings.local_plugins_allowed,
        permissions_network: settings.permissions_network,
        code_execute: settings.code_execute,
        audit_retention_days: settings.audit_retention_days,
        audit_enabled: settings.audit_enabled,
        provider_sets_locked: settings.provider_sets_locked,
        allowed_provider_set_ids: settings.allowed_provider_set_ids,
    };
    save_settings(&app, &to_persist)?;
    Ok(to_persist)
}

fn validate_active_set_id(
    sets: &Option<Vec<ProviderSetEntry>>,
    active_set_id: Option<String>,
) -> Option<String> {
    let Some(sets) = sets else {
        return None;
    };
    let active = active_set_id?;
    if sets.iter().any(|s| s.id == active) {
        Some(active)
    } else {
        None
    }
}
