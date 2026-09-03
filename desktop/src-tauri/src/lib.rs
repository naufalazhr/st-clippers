use std::io::BufRead;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::Manager;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
mod menu;
mod tray;

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

/// Kill backends orphaned by a crash or force-quit.
///
/// `kill_backend` only runs on a clean window close, so a crashed run leaves the
/// old sidecar holding port 8010. The freshly spawned backend then exits with
/// "address already in use" while the app keeps talking to the stale build — which
/// is how an upgraded app still answered with an old crop_mode enum and old
/// bundled codecs. Only our own binary name is targeted.
fn kill_orphan_backends() {
    #[cfg(windows)]
    let mut command = {
        let mut c = Command::new("taskkill");
        c.args(["/F", "/IM", "sultanclip-backend.exe"]);
        c.creation_flags(CREATE_NO_WINDOW);
        c
    };
    #[cfg(not(windows))]
    let mut command = {
        let mut c = Command::new("pkill");
        c.args(["-f", "sultanclip-backend"]);
        c
    };

    if let Ok(status) = command.stdout(Stdio::null()).stderr(Stdio::null()).status() {
        if status.success() {
            println!("[tauri] Cleared an orphaned backend still holding the port");
        }
    }
}

fn spawn_backend(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    kill_orphan_backends();

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
        .env("SULTANCLIP_APP_VERSION", app.package_info().version.to_string())
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

pub fn kill_backend(app: &tauri::AppHandle) {
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
            if let Err(e) = tray::setup(app.handle()) {
                eprintln!("[tauri] Failed to build tray: {}", e);
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // With MCP enabled the backend has to keep answering tool calls
                // after the window is gone, so closing hides to the tray. With
                // MCP off, closing quits exactly as it did before.
                if window.label() == "main" && tray::mcp_enabled() {
                    api.prevent_close();
                    let _ = window.hide();
                } else {
                    kill_backend(window.app_handle());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // CloseRequested alone misses quits that skip the window close path
            // (Cmd+Q, app relaunch), which is what orphans the sidecar.
            if let tauri::RunEvent::Exit = event {
                kill_backend(app_handle);
            }
        });
}
