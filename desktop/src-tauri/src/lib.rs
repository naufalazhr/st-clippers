use std::io::BufRead;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::Manager;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
mod menu;

/// Windows CREATE_NO_WINDOW: the backend is a console app, so without this flag a
/// console window pops up next to the app and closing it kills the backend.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

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

fn backend_exe_name() -> &'static str {
    if cfg!(windows) {
        "sultanclip-backend.exe"
    } else {
        "sultanclip-backend"
    }
}

fn dir_has_backend(dir: &PathBuf) -> bool {
    dir.join(backend_exe_name()).exists() || dir.join("sultanclip-backend").exists()
}

fn get_backend_dir(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let resource_dir = app.path().resource_dir()?;
    let candidates = [
        resource_dir.join("sultanclip-backend"),
        resource_dir.join("resources/sultanclip-backend"),
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("resources/sultanclip-backend"),
    ];
    for path in &candidates {
        if dir_has_backend(path) {
            return Ok(path.clone());
        }
    }
    Err(format!(
        "Backend binary not found (tried {:?})",
        candidates
    )
    .into())
}

fn spawn_backend(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let backend_dir = get_backend_dir(app)?;
    let backend_exe = {
        let win = backend_dir.join("sultanclip-backend.exe");
        let unix = backend_dir.join("sultanclip-backend");
        if win.exists() {
            win
        } else {
            unix
        }
    };

    let mut command = Command::new(&backend_exe);
    command
        .args(["--port", "8010"])
        .current_dir(&backend_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let mut child = command.spawn()?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::Other, "no stdout"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::Other, "no stderr"))?;

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

    // Uvicorn writes its access log to stderr. Nothing reads it, so once the OS
    // pipe buffer fills the backend blocks on write and stops serving requests
    // (every fetch then fails). Drain it and mirror it to our own stderr.
    std::thread::spawn(move || {
        let reader = std::io::BufReader::new(stderr);
        for line in reader.lines() {
            match line {
                Ok(line) => eprintln!("[backend] {}", line),
                Err(e) => {
                    eprintln!("[tauri] Error reading backend stderr: {}", e);
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
            if let Err(e) = menu::build_menu(app) {
                eprintln!("[tauri] Failed to build menu: {}", e);
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
