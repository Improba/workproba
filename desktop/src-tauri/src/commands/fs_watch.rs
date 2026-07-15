use std::path::{Path, PathBuf};
use std::sync::Mutex;

use notify::event::{CreateKind, ModifyKind, RemoveKind, RenameMode};
use notify::{Config, Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

use super::workspace_store::WORKPROBA_DIR_NAME;

#[derive(Default)]
pub struct FsWatchState {
    pub watcher: Mutex<Option<RecommendedWatcher>>,
    pub root: Mutex<Option<PathBuf>>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FsChangePayload {
    pub kind: String,
    pub path: String,
    pub is_dir: bool,
}

pub fn stop_fs_watch(state: &FsWatchState) {
    if let Ok(mut watcher) = state.watcher.lock() {
        *watcher = None;
    }
    if let Ok(mut root) = state.root.lock() {
        *root = None;
    }
}

pub fn start_fs_watch(app: &AppHandle, root: &Path) {
    let state = app.state::<FsWatchState>();
    stop_fs_watch(&state);

    let root = match root.canonicalize() {
        Ok(path) => path,
        Err(error) => {
            log::warn!("fs watch: impossible de canoniser la racine {root:?}: {error}");
            root.to_path_buf()
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
            log::warn!("fs watch: impossible de créer le watcher: {error}");
            return;
        }
    };

    if let Err(error) = watcher.watch(&root, RecursiveMode::Recursive) {
        log::warn!("fs watch: impossible d'observer {root:?}: {error}");
        return;
    }

    if let Ok(mut stored_root) = state.root.lock() {
        *stored_root = Some(root);
    }
    match state.watcher.lock() {
        Ok(mut stored_watcher) => {
            *stored_watcher = Some(watcher);
        }
        Err(error) => {
            log::warn!("fs watch: impossible de stocker le watcher: {error}");
        }
    };
}

fn handle_notify_event(app: &AppHandle, root: &Path, event: Event) {
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

fn emit_rename_events(app: &AppHandle, root: &Path, mode: RenameMode, paths: &[PathBuf]) {
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

fn emit_fs_change(app: &AppHandle, payload: FsChangePayload) {
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
