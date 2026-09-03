//! Tray residency.
//!
//! When MCP is enabled the backend must keep serving tool calls after the user
//! closes the window, so closing hides instead of quitting. That is only
//! acceptable with a visible way back and an explicit Quit -- otherwise the only
//! way out is Task Manager.
//!
//! When MCP is off, closing quits exactly as it always did.

use std::fs;
use std::path::PathBuf;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Manager};

/// Reads the same mcp.json the backend writes, so the two agree on whether the
/// app should stay resident without needing a channel between them.
pub fn mcp_enabled() -> bool {
    let Some(path) = mcp_config_path() else {
        return false;
    };
    let Ok(raw) = fs::read_to_string(path) else {
        return false;
    };
    parse_enabled(&raw)
}

/// A missing, unreadable or malformed config means "not enabled": the app must
/// fall back to quitting on close rather than silently becoming resident.
fn parse_enabled(raw: &str) -> bool {
    serde_json::from_str::<serde_json::Value>(raw)
        .ok()
        .and_then(|v| v.get("enabled").and_then(|e| e.as_bool()))
        .unwrap_or(false)
}

fn mcp_config_path() -> Option<PathBuf> {
    // Mirrors resolve_data_dir() in api.py.
    if let Ok(dir) = std::env::var("SULTANCLIP_DATA_DIR") {
        return Some(PathBuf::from(dir).join("mcp.json"));
    }
    #[cfg(windows)]
    {
        std::env::var("APPDATA")
            .ok()
            .map(|d| PathBuf::from(d).join("SultanClip").join("mcp.json"))
    }
    #[cfg(target_os = "macos")]
    {
        std::env::var("HOME").ok().map(|h| {
            PathBuf::from(h)
                .join("Library")
                .join("Application Support")
                .join("SultanClip")
                .join("mcp.json")
        })
    }
    #[cfg(all(not(windows), not(target_os = "macos")))]
    {
        None
    }
}

pub fn setup(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "tray.show", "Buka Sultan Clip", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "tray.quit", "Keluar", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;

    TrayIconBuilder::with_id("main")
        .icon(app.default_window_icon().unwrap().clone())
        .tooltip("Sultan Clip")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "tray.show" => show_main_window(app),
            "tray.quit" => {
                crate::kill_backend(app);
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            // Left click reopens the window, which is what a hidden-to-tray app
            // is expected to do on Windows.
            if let tauri::tray::TrayIconEvent::Click {
                button: tauri::tray::MouseButton::Left,
                button_state: tauri::tray::MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}

pub fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

#[cfg(test)]
mod tests {
    use super::parse_enabled;

    #[test]
    fn enabled_only_when_the_config_says_so() {
        assert!(parse_enabled(r#"{"enabled": true, "port": 8765}"#));
        assert!(!parse_enabled(r#"{"enabled": false, "port": 8765}"#));
    }

    #[test]
    fn anything_unreadable_means_not_resident() {
        // Closing must keep quitting unless MCP is definitely on.
        assert!(!parse_enabled(""));
        assert!(!parse_enabled("{not json"));
        assert!(!parse_enabled("{}"));
        assert!(!parse_enabled("null"));
        assert!(!parse_enabled(r#"{"enabled": "yes"}"#));
    }
}
