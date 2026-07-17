use std::path::{Path, PathBuf};
use std::sync::Mutex;

use notify::event::{CreateKind, ModifyKind, RemoveKind, RenameMode};
use notify::{Config, Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use super::workspace_store::WORKPROBA_DIR_NAME;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum FsWatchStatus {
    #[default]
    Inactive,
    Active,
    Degraded,
}

#[derive(Default)]
pub struct FsWatchState {
    pub watcher: Mutex<Option<RecommendedWatcher>>,
    pub root: Mutex<Option<PathBuf>>,
    pub status: Mutex<FsWatchStatus>,
    pub last_error: Mutex<Option<String>>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FsChangePayload {
    pub kind: String,
    pub path: String,
    pub is_dir: bool,
}

fn set_watch_status(state: &FsWatchState, status: FsWatchStatus, error: Option<String>) {
    if let Ok(mut stored_status) = state.status.lock() {
        *stored_status = status;
    }
    if let Ok(mut stored_error) = state.last_error.lock() {
        *stored_error = error;
    }
}

pub fn stop_fs_watch(state: &FsWatchState) {
    if let Ok(mut watcher) = state.watcher.lock() {
        *watcher = None;
    }
    if let Ok(mut root) = state.root.lock() {
        *root = None;
    }
    set_watch_status(state, FsWatchStatus::Inactive, None);
}

pub fn start_fs_watch<R: Runtime>(app: &AppHandle<R>, root: &Path) -> FsWatchStatus {
    let state = app.state::<FsWatchState>();
    stop_fs_watch(&state);

    if let Ok(mut stored_root) = state.root.lock() {
        *stored_root = Some(root.to_path_buf());
    }

    let root = match root.canonicalize() {
        Ok(path) => path,
        Err(error) => {
            let message = format!("impossible de canoniser la racine {root:?}: {error}");
            log::warn!("fs watch: {message}");
            set_watch_status(&state, FsWatchStatus::Degraded, Some(message));
            return FsWatchStatus::Degraded;
        }
    };

    let app_handle = app.clone();
    let watch_root = root.clone();

    let mut watcher = match RecommendedWatcher::new(
        move |result: Result<Event, notify::Error>| {
            let app = app_handle.clone();
            let watch_root = watch_root.clone();
            match result {
                Ok(event) => handle_notify_event(&app, &watch_root, event),
                Err(error) => log::warn!("fs watch: erreur notify: {error}"),
            }
        },
        Config::default(),
    ) {
        Ok(watcher) => watcher,
        Err(error) => {
            let message = format!("impossible de créer le watcher: {error}");
            log::warn!("fs watch: {message}");
            set_watch_status(&state, FsWatchStatus::Degraded, Some(message));
            return FsWatchStatus::Degraded;
        }
    };

    if let Err(error) = watcher.watch(&root, RecursiveMode::Recursive) {
        let message = format!("impossible d'observer {root:?}: {error}");
        log::warn!("fs watch: {message}");
        set_watch_status(&state, FsWatchStatus::Degraded, Some(message));
        return FsWatchStatus::Degraded;
    }

    if let Ok(mut stored_root) = state.root.lock() {
        *stored_root = Some(root.clone());
    }
    let status = match state.watcher.lock() {
        Ok(mut stored_watcher) => {
            *stored_watcher = Some(watcher);
            set_watch_status(&state, FsWatchStatus::Active, None);
            FsWatchStatus::Active
        }
        Err(error) => {
            let message = format!("impossible de stocker le watcher: {error}");
            log::warn!("fs watch: {message}");
            set_watch_status(&state, FsWatchStatus::Degraded, Some(message));
            FsWatchStatus::Degraded
        }
    };
    status
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FsWatchStatusPayload {
    pub status: FsWatchStatus,
    pub last_error: Option<String>,
}

pub fn current_fs_watch_status(state: &FsWatchState) -> FsWatchStatusPayload {
    let status = state
        .status
        .lock()
        .map(|guard| *guard)
        .unwrap_or_default();
    let last_error = state
        .last_error
        .lock()
        .ok()
        .and_then(|guard| guard.clone());
    FsWatchStatusPayload { status, last_error }
}

#[tauri::command]
pub fn get_fs_watch_status<R: Runtime>(app: AppHandle<R>) -> Result<FsWatchStatusPayload, String> {
    Ok(current_fs_watch_status(&app.state::<FsWatchState>()))
}

#[tauri::command]
pub fn retry_fs_watch<R: Runtime>(app: AppHandle<R>) -> Result<FsWatchStatusPayload, String> {
    let state = app.state::<FsWatchState>();
    let root_path = state
        .root
        .lock()
        .map_err(|_| "Impossible de verrouiller l'état fs watch".to_string())?
        .clone();
    if let Some(path) = root_path {
        start_fs_watch(&app, &path);
    }
    Ok(current_fs_watch_status(&state))
}

fn handle_notify_event<R: Runtime>(app: &AppHandle<R>, root: &Path, event: Event) {
    match event.kind {
        EventKind::Modify(ModifyKind::Name(mode)) => {
            emit_rename_events(app, root, mode, &event.paths);
        }
        EventKind::Create(_) => {
            for path in &event.paths {
                if let Some(payload) = build_payload(root, &event.kind, path) {
                    emit_fs_change(app, payload);
                }
            }
        }
        EventKind::Modify(_) => {
            for path in &event.paths {
                if let Some(payload) = build_payload(root, &event.kind, path) {
                    emit_fs_change(app, payload);
                }
            }
        }
        EventKind::Remove(_) => {
            for path in &event.paths {
                if let Some(payload) = build_payload(root, &event.kind, path) {
                    emit_fs_change(app, payload);
                }
            }
        }
        _ => {}
    }
}

fn emit_rename_events<R: Runtime>(app: &AppHandle<R>, root: &Path, mode: RenameMode, paths: &[PathBuf]) {
    match mode {
        RenameMode::Both if paths.len() >= 2 => {
            if let Some(old_payload) =
                build_payload(root, &EventKind::Remove(RemoveKind::Any), &paths[0])
            {
                emit_fs_change(
                    app,
                    FsChangePayload {
                        kind: "delete".to_string(),
                        ..old_payload
                    },
                );
            }
            if let Some(new_payload) =
                build_payload(root, &EventKind::Create(CreateKind::Any), &paths[1])
            {
                emit_fs_change(
                    app,
                    FsChangePayload {
                        kind: "create".to_string(),
                        ..new_payload
                    },
                );
            }
        }
        RenameMode::From => {
            for path in paths {
                if let Some(payload) =
                    build_payload(root, &EventKind::Remove(RemoveKind::Any), path)
                {
                    emit_fs_change(
                        app,
                        FsChangePayload {
                            kind: "delete".to_string(),
                            ..payload
                        },
                    );
                }
            }
        }
        RenameMode::To => {
            for path in paths {
                if let Some(payload) =
                    build_payload(root, &EventKind::Create(CreateKind::Any), path)
                {
                    emit_fs_change(
                        app,
                        FsChangePayload {
                            kind: "create".to_string(),
                            ..payload
                        },
                    );
                }
            }
        }
        _ => {
            for path in paths {
                if let Some(payload) =
                    build_payload(root, &EventKind::Modify(ModifyKind::Any), path)
                {
                    emit_fs_change(app, payload);
                }
            }
        }
    }
}

fn emit_fs_change<R: Runtime>(app: &AppHandle<R>, payload: FsChangePayload) {
    if let Err(error) = app.emit("fs-change", payload) {
        log::warn!("fs watch: émission fs-change impossible: {error}");
    }
}

fn build_payload(root: &Path, kind: &EventKind, path: &Path) -> Option<FsChangePayload> {
    let relative = relative_path(root, path)?;
    if should_ignore_relative(&relative) {
        return None;
    }

    let payload_kind = match kind {
        EventKind::Create(_) => "create",
        EventKind::Modify(_) => "modify",
        EventKind::Remove(_) => "delete",
        _ => return None,
    };

    Some(FsChangePayload {
        kind: payload_kind.to_string(),
        path: relative,
        is_dir: is_dir_from_event(kind, path),
    })
}

fn relative_path(root: &Path, path: &Path) -> Option<String> {
    let canonical_path = path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
    let canonical_root = root.canonicalize().unwrap_or_else(|_| root.to_path_buf());

    if !canonical_path.starts_with(&canonical_root) {
        return None;
    }

    let relative = canonical_path
        .strip_prefix(&canonical_root)
        .ok()?
        .to_string_lossy()
        .replace('\\', "/");

    Some(relative)
}

fn should_ignore_relative(relative: &str) -> bool {
    if relative.is_empty() {
        return true;
    }

    relative.split('/').any(|segment| {
        segment.is_empty() || segment.starts_with('.') || segment == WORKPROBA_DIR_NAME
    })
}

fn is_dir_from_event(kind: &EventKind, path: &Path) -> bool {
    match kind {
        EventKind::Create(CreateKind::Folder) | EventKind::Remove(RemoveKind::Folder) => true,
        EventKind::Create(CreateKind::File) | EventKind::Remove(RemoveKind::File) => false,
        _ => path.is_dir(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::mpsc;
    use std::thread;
    use std::time::Duration;
    use tauri::test::{mock_builder, mock_context, noop_assets};
    use uuid::Uuid;

    fn temp_watch_dir() -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "workproba_fs_watch_test_{}",
            Uuid::new_v4().simple()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    fn build_test_app() -> tauri::App<tauri::test::MockRuntime> {
        mock_builder()
            .manage(FsWatchState::default())
            .build(mock_context(noop_assets()))
            .expect("build test app")
    }

    #[test]
    fn retry_fs_watch_after_start_completes_without_deadlock() {
        let app = build_test_app();
        let dir = temp_watch_dir();
        let handle = app.handle().clone();

        let initial = start_fs_watch(&handle, &dir);
        assert_ne!(initial, FsWatchStatus::Inactive);

        let (tx, rx) = mpsc::channel();
        let retry_handle = handle.clone();
        thread::spawn(move || {
            let result = retry_fs_watch(retry_handle);
            let _ = tx.send(result);
        });

        match rx.recv_timeout(Duration::from_secs(5)) {
            Ok(result) => {
                assert!(result.is_ok(), "retry_fs_watch should succeed: {:?}", result);
                let payload = result.unwrap();
                assert_ne!(payload.status, FsWatchStatus::Inactive);
            }
            Err(_) => panic!("retry_fs_watch deadlocked or timed out after 5s"),
        }

        let _ = fs::remove_dir_all(dir);
    }
}
