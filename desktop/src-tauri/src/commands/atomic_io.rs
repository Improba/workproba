use std::fs;
use std::path::{Path, PathBuf};

/// Écriture atomique : fichier temporaire + rename sur le même volume.
pub fn atomic_write(path: &Path, content: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let temp_path = {
        let mut temp = path.as_os_str().to_os_string();
        temp.push(".tmp");
        PathBuf::from(temp)
    };
    fs::write(&temp_path, content).map_err(|error| error.to_string())?;
    fs::rename(&temp_path, path).map_err(|error| error.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use uuid::Uuid;

    fn unique_temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "workproba_atomic_test_{name}_{}",
            Uuid::new_v4().simple()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    #[test]
    fn atomic_write_writes_and_reads_back() {
        let root = unique_temp_dir("write");
        let nested = root.join("nested").join("data.json");
        let content = r#"{"ok":true}"#;

        atomic_write(&nested, content).expect("atomic_write");

        assert!(nested.is_file());
        assert_eq!(fs::read_to_string(&nested).expect("read"), content);
        assert!(!nested.with_extension("tmp").exists());

        let _ = fs::remove_dir_all(root);
    }
}
