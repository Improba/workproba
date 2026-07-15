pub mod atomic_io;
pub mod audit;
pub mod fs_watch;
pub mod plugins;
pub mod preset;
pub mod project;
pub mod settings_store;
pub mod workspace_store;

pub use fs_watch::FsWatchState;
pub use plugins::{
    activate_plugin, deactivate_plugin, get_plugin_data_dir, install_local_plugin, list_plugins,
    uninstall_local_plugin, PluginInfo, PluginManifest,
};
pub use preset::{get_enterprise_preset, is_preset_active, EnterprisePreset};
pub use project::{
    create_conversation, delete_conversation, ensure_workproba_dir, find_conversation_by_id,
    get_active_project_path, get_conversation, get_workproba_dir, get_workspace_data_dir,
    get_workspace_info, list_conversations, list_dir_entries, list_documents, list_workspaces,
    open_path, pick_project_folder, restore_last_project_path, reveal_in_os, save_conversation,
    set_active_project_path, update_workspace_title, ProjectState,
};
pub use settings_store::{
    builtin_provider_sets, get_app_settings, save_app_settings, AppSettings, LlmProviderEntry,
    ProviderSetEntry,
};
pub use workspace_store::{ConversationSession, WorkspaceInfo};
