use std::fs;
use std::path::{Path, PathBuf};

use chrono::Utc;
use serde_json::{json, Value};

const AUDIT_SUBDIR: &str = "audit";
const AUDIT_FILENAME: &str = "audit.jsonl";

pub fn audit_file_path(app_data: &Path) -> PathBuf {
    app_data.join(AUDIT_SUBDIR).join(AUDIT_FILENAME)
}

pub fn log_audit_event(
    app_data: &Path,
    event: &str,
    actor: &str,
    details: Value,
) -> Result<(), String> {
    let dir = app_data.join(AUDIT_SUBDIR);
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    let path = audit_file_path(app_data);
    let entry = json!({
        "timestamp": Utc::now().to_rfc3339(),
        "event": event,
        "actor": actor,
        "details": details,
    });
    let line = serde_json::to_string(&entry).map_err(|error| error.to_string())?;
    use std::io::Write;
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|error| error.to_string())?;
    writeln!(file, "{line}").map_err(|error| error.to_string())?;
    Ok(())
}

#[cfg(test)]
mod audit_tests {
    use super::*;
    use uuid::Uuid;

    fn temp_app_data() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("wp_audit_test_{}", Uuid::new_v4()));
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    #[test]
    fn log_audit_event_appends_jsonl_line() {
        let app_data = temp_app_data();
        log_audit_event(
            &app_data,
            "plugin.activated",
            "user",
            json!({"plugin_id": "workproba.projet"}),
        )
        .expect("log");
        let raw = fs::read_to_string(audit_file_path(&app_data)).expect("read");
        assert!(raw.contains("plugin.activated"));
        assert!(raw.contains("workproba.projet"));
    }
}
