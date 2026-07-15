mod commands;
mod sidecar;

use commands::{
    activate_plugin, create_conversation, deactivate_plugin, delete_conversation,
    ensure_workproba_dir, find_conversation_by_id, get_active_project_path, get_app_settings,
    get_conversation, get_enterprise_preset, get_plugin_data_dir, get_workproba_dir,
    get_workspace_data_dir, get_workspace_info, install_local_plugin, is_preset_active,
    list_conversations, list_dir_entries, list_documents, list_plugins, list_workspaces, open_path,
    pick_project_folder, restore_last_project_path, reveal_in_os, save_app_settings,
    save_conversation, set_active_project_path, uninstall_local_plugin, update_workspace_title,
    FsWatchState, ProjectState,
};
use sidecar::{ai_sidecar_status, spawn_packaged_sidecar, start_ai_sidecar, try_spawn_dev_uvicorn};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(ProjectState::default())
        .manage(FsWatchState::default())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
                log::info!(
                    "Dev sidecar: lancez `make dev-ai` ou `cd services/ai && ./run_dev.sh` (port 8765). \
                     Option: PYTHON_SIDECAR_AUTO_START=1 pour lancer via services/ai/.venv/bin/python."
                );
                if std::env::var("PYTHON_SIDECAR_AUTO_START").is_ok() {
                    if let Err(error) = try_spawn_dev_uvicorn() {
                        log::warn!("PYTHON_SIDECAR_AUTO_START: {error}");
                    } else {
                        log::info!(
                            "PYTHON_SIDECAR_AUTO_START: sidecar lancé via services/ai/.venv (port 8765)"
                        );
                    }
                }
            } else if let Err(error) = spawn_packaged_sidecar(app.handle()) {
                eprintln!("Sidecar empaqueté: {error}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            pick_project_folder,
            set_active_project_path,
            get_active_project_path,
            restore_last_project_path,
            get_workproba_dir,
            ensure_workproba_dir,
            get_workspace_info,
            get_workspace_data_dir,
            list_workspaces,
            update_workspace_title,
            list_conversations,
            get_conversation,
            find_conversation_by_id,
            save_conversation,
            delete_conversation,
            create_conversation,
            list_documents,
            list_dir_entries,
            open_path,
            reveal_in_os,
            start_ai_sidecar,
            ai_sidecar_status,
            get_app_settings,
            save_app_settings,
            list_plugins,
            activate_plugin,
            deactivate_plugin,
            get_plugin_data_dir,
            install_local_plugin,
            uninstall_local_plugin,
            get_enterprise_preset,
            is_preset_active,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
