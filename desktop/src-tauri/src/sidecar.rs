use serde::Serialize;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::Command as SidecarCommand;
use tauri_plugin_shell::ShellExt;

const SIDECAR_NAME: &str = "binaries/workproba-ai";

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarStatus {
    pub name: String,
    pub running: bool,
    pub port: u16,
    pub message: String,
}

/// True si le dossier contient un build Playwright `chromium-<revision>`.
pub fn is_bundled_chromium_dir(path: &Path) -> bool {
    if !path.is_dir() {
        return false;
    }
    match std::fs::read_dir(path) {
        Ok(entries) => entries.flatten().any(|entry| {
            let name = entry.file_name();
            let name = name.to_string_lossy();
            entry.file_type().map(|kind| kind.is_dir()).unwrap_or(false)
                && name.starts_with("chromium-")
        }),
        Err(_) => false,
    }
}

fn packaged_playwright_browsers_dir(app: &AppHandle) -> Option<PathBuf> {
    let resource = app.path().resource_dir().ok()?;
    let candidates = [
        resource.join("ms-playwright"),
        resource.join("resources").join("ms-playwright"),
    ];
    candidates
        .into_iter()
        .find(|path| is_bundled_chromium_dir(path))
}

fn repo_playwright_browsers_dir() -> Option<PathBuf> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let candidate = manifest_dir.join("resources").join("ms-playwright");
    is_bundled_chromium_dir(&candidate).then_some(candidate)
}

fn with_chromium_env(command: SidecarCommand, browsers: Option<PathBuf>) -> SidecarCommand {
    match browsers {
        Some(path) => command
            .env("PLAYWRIGHT_BROWSERS_PATH", path.as_os_str())
            .env("WORKPROBA_CHROMIUM_BUNDLED", "1")
            .env("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1"),
        None => {
            eprintln!("Chromium bundlé introuvable (PDF HTML et navigateur en repli ReportLab)");
            command
        }
    }
}

/// Démarre le sidecar Python empaqueté via `externalBin` (build release).
pub fn spawn_packaged_sidecar(app: &AppHandle) -> Result<(), String> {
    match app.shell().sidecar(SIDECAR_NAME) {
        Ok(command) => {
            with_chromium_env(command, packaged_playwright_browsers_dir(app))
                .spawn()
                .map_err(|error| error.to_string())?;
            Ok(())
        }
        Err(error) => Err(format!("Sidecar empaqueté indisponible: {error}")),
    }
}

/// Démarre le sidecar Python (services/ai) une fois empaqueté via `externalBin`.
/// En développement, le front Quasar appelle plutôt le service Python lancé manuellement.
#[tauri::command]
pub async fn start_ai_sidecar(app: AppHandle) -> Result<SidecarStatus, String> {
    match app.shell().sidecar(SIDECAR_NAME) {
        Ok(command) => {
            with_chromium_env(command, packaged_playwright_browsers_dir(&app))
                .spawn()
                .map_err(|error| error.to_string())?;
            Ok(SidecarStatus {
                name: SIDECAR_NAME.to_string(),
                running: true,
                port: 8765,
                message: "Sidecar Python démarré".to_string(),
            })
        }
        Err(error) => Ok(SidecarStatus {
            name: SIDECAR_NAME.to_string(),
            running: false,
            port: 8765,
            message: format!(
                "Sidecar indisponible en dev ({error}). Lancez services/ai manuellement."
            ),
        }),
    }
}

const DEV_SIDECAR_PORT: u16 = 8765;
const SIDECAR_LIVENESS_TIMEOUT: Duration = Duration::from_millis(500);

/// Sonde la vivacité du sidecar via une ouverture TCP contrôlée en timeout.
/// Extrait de `ai_sidecar_status` pour rester testable hors contexte Tauri.
pub fn check_sidecar_liveness(addr: SocketAddr, timeout: Duration) -> bool {
    TcpStream::connect_timeout(&addr, timeout).is_ok()
}

#[tauri::command]
pub fn ai_sidecar_status() -> Result<SidecarStatus, String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], DEV_SIDECAR_PORT));

    let running = check_sidecar_liveness(addr, SIDECAR_LIVENESS_TIMEOUT);
    let message = if running {
        format!("Sidecar Python accessible sur le port {DEV_SIDECAR_PORT}")
    } else {
        format!("Sidecar Python inaccessible sur le port {DEV_SIDECAR_PORT}")
    };

    Ok(SidecarStatus {
        name: SIDECAR_NAME.to_string(),
        running,
        port: DEV_SIDECAR_PORT,
        message,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    fn loopback(port: u16) -> SocketAddr {
        SocketAddr::from(([127, 0, 0, 1], port))
    }

    #[test]
    fn liveness_true_quand_un_listener_occupe_le_port() {
        let listener = TcpListener::bind(loopback(0)).expect("bind ephemeral");
        let addr = listener.local_addr().expect("local addr");

        assert!(check_sidecar_liveness(addr, SIDECAR_LIVENESS_TIMEOUT));
    }

    #[test]
    fn liveness_false_quand_aucun_listener_n_occupe_le_port() {
        // On cherche un port libéré puis on sonde ; on tolère une éventuelle
        // réattribution immédiate par l'OS en testant quelques candidats.
        for _ in 0..16 {
            let candidate = {
                let probe = TcpListener::bind(loopback(0)).expect("bind ephemeral");
                let addr = probe.local_addr().expect("local addr");
                drop(probe);
                addr
            };

            if !check_sidecar_liveness(candidate, SIDECAR_LIVENESS_TIMEOUT) {
                return;
            }
        }

        panic!("aucun port libéré n'est resté injoignable (race OS)");
    }

    #[test]
    fn bundled_chromium_dir_detecte_un_dossier_chromium() {
        let dir = std::env::temp_dir().join(format!(
            "wp-chromium-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        let chrome = dir.join("chromium-1148");
        std::fs::create_dir_all(&chrome).expect("mkdir");
        assert!(is_bundled_chromium_dir(&dir));
        assert!(!is_bundled_chromium_dir(&chrome.join("missing")));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn bundled_chromium_dir_ignore_headless_shell_seul() {
        let dir = std::env::temp_dir().join(format!(
            "wp-chromium-hs-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        let shell = dir.join("chromium_headless_shell-1228");
        std::fs::create_dir_all(&shell).expect("mkdir");
        assert!(!is_bundled_chromium_dir(&dir));
        let _ = std::fs::remove_dir_all(&dir);
    }
}

/// Tente de lancer uvicorn en dev si PYTHON_SIDECAR_AUTO_START est défini.
pub fn try_spawn_dev_uvicorn() -> Result<(), String> {
    let services_ai = locate_services_ai_dir()?;
    let port = DEV_SIDECAR_PORT.to_string();
    let uvicorn_app_args = [
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        &port,
        "--reload",
    ];

    let venv_python = services_ai.join(".venv/bin/python");
    let venv_uvicorn = services_ai.join(".venv/bin/uvicorn");

    let mut command = if venv_python.is_file() {
        let mut cmd = Command::new(&venv_python);
        cmd.args(["-m", "uvicorn"]);
        cmd.args(uvicorn_app_args);
        cmd
    } else if venv_uvicorn.is_file() {
        let mut cmd = Command::new(&venv_uvicorn);
        cmd.args(uvicorn_app_args);
        cmd
    } else {
        let mut cmd = Command::new("python3");
        cmd.args(["-m", "uvicorn"]);
        cmd.args(uvicorn_app_args);
        cmd
    };

    if let Some(browsers) = repo_playwright_browsers_dir() {
        command.env("PLAYWRIGHT_BROWSERS_PATH", &browsers);
        command.env("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1");
    }

    command
        .current_dir(&services_ai)
        .spawn()
        .map_err(|error| format!("impossible de lancer le sidecar Python: {error}"))?;

    Ok(())
}

fn locate_services_ai_dir() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let from_desktop = manifest_dir
        .parent()
        .and_then(|desktop| desktop.parent())
        .map(|root| root.join("services/ai"));

    if let Some(path) = from_desktop.filter(|candidate| candidate.is_dir()) {
        return Ok(path);
    }

    std::env::current_dir()
        .map(|cwd| cwd.join("services/ai"))
        .map_err(|error| error.to_string())
}
