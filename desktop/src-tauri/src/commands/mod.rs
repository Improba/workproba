pub mod fs_watch;
pub mod project;
pub mod settings_store;
pub mod workspace_store;

pub use fs_watch::FsWatchState;
pub use project::{
    create_conversation, delete_conversation, ensure_workproba_dir, find_conversation_by_id,
    get_active_project_path, get_conversation, get_workproba_dir, get_workspace_data_dir,
    get_workspace_info, list_conversations, list_dir_entries, list_documents, list_workspaces,
    open_path, pick_project_folder, restore_last_project_path, reveal_in_os, save_conversation,
    set_active_project_path, ProjectState,
};
pub use workspace_store::{ConversationSession, WorkspaceInfo};
pub use settings_store::{AppSettings, LlmProviderEntry, get_app_settings, save_app_settings};
