use std::io::BufRead;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::Manager;

struct BackendProcess {
    child: Mutex<Option<Child>>,
    ready: AtomicBool,
}

impl BackendProcess {
    fn new() -> Self {
        Self {
            child: Mutex::new(None),
            ready: AtomicBool::new(false),
        }
    }
}

fn get_backend_dir(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let resource_dir = app.path().resource_dir()?;
    let prod_path = resource_dir.join("sultanclip-backend");
    if prod_path.join("sultanclip-backend").exists() {
        return Ok(prod_path);
    }
    let dev_path = resource_dir.join("resources/sultanclip-backend");
    if dev_path.join("sultanclip-backend").exists() {
        return Ok(dev_path);
    }
    let cargo_path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("resources/sultanclip-backend");
    if cargo_path.join("sultanclip-backend").exists() {
        return Ok(cargo_path);
    }
    Err(format!(
        "Backend binary not found (tried {:?}, {:?}, {:?})",
        prod_path, dev_path, cargo_path
    )
    .into())
}

fn spawn_backend(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let backend_dir = get_backend_dir(app)?;
    let backend_exe = backend_dir.join("sultanclip-backend");

    let mut child = Command::new(&backend_exe)
        .args(["--port", "8010"])
        .current_dir(&backend_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::Other, "no stdout"))?;

    let handle = app.handle().clone();
    *app.state::<BackendProcess>().child.lock().unwrap() = Some(child);

    std::thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(line) => {
                    println!("[backend] {}", line);
                    if line.contains("SULTANCLIP_READY") {
                        handle
                            .state::<BackendProcess>()
                            .ready
                            .store(true, Ordering::SeqCst);
                        println!("[tauri] Backend ready signal received");
                    }
                }
                Err(e) => {
                    eprintln!("[tauri] Error reading backend stdout: {}", e);
                    break;
                }
            }
        }
    });

    Ok(())
}

fn kill_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendProcess>();
    if let Ok(mut guard) = state.child.lock() {
        if let Some(ref mut child) = *guard {
            let _ = child.kill();
            let _ = child.wait();
        }
    };
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess::new())
        .setup(|app| {
            if let Err(e) = spawn_backend(app) {
                eprintln!("[tauri] Failed to start backend: {}", e);
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                kill_backend(window.app_handle());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
