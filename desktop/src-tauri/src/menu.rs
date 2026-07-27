use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::Emitter;

#[derive(Clone, serde::Serialize)]
struct MenuAction {
    item_id: String,
}

pub fn build_menu(app: &tauri::App) -> tauri::Result<()> {
    let new_job = MenuItemBuilder::new("New Clip Job")
        .id("file.new-job")
        .accelerator("CmdOrCtrl+N")
        .build(app)?;
    let open_video = MenuItemBuilder::new("Open Video\u{2026}")
        .id("file.open-video")
        .accelerator("CmdOrCtrl+O")
        .build(app)?;
    let file_sub = SubmenuBuilder::new(app, "File")
        .item(&new_job)
        .item(&open_video)
        .separator()
        .item(&PredefinedMenuItem::close_window(app, None)?)
        .build()?;

    let edit_sub = SubmenuBuilder::new(app, "Edit")
        .item(&PredefinedMenuItem::undo(app, None)?)
        .separator()
        .item(&PredefinedMenuItem::redo(app, None)?)
        .separator()
        .item(&PredefinedMenuItem::cut(app, None)?)
        .item(&PredefinedMenuItem::copy(app, None)?)
        .item(&PredefinedMenuItem::paste(app, None)?)
        .separator()
        .item(&PredefinedMenuItem::select_all(app, None)?)
        .build()?;

    let refresh = MenuItemBuilder::new("Refresh")
        .id("view.refresh")
        .accelerator("CmdOrCtrl+R")
        .build(app)?;
    let toggle_theme = MenuItemBuilder::new("Toggle Theme")
        .id("view.theme")
        .accelerator("CmdOrCtrl+Shift+T")
        .build(app)?;
    let toggle_sidebar = MenuItemBuilder::new("Toggle Sidebar")
        .id("view.sidebar")
        .accelerator("CmdOrCtrl+B")
        .build(app)?;
    let toggle_statusbar = MenuItemBuilder::new("Toggle Status Bar")
        .id("view.statusbar")
        .build(app)?;
    let view_sub = SubmenuBuilder::new(app, "View")
        .item(&refresh)
        .item(&toggle_theme)
        .separator()
        .item(&toggle_sidebar)
        .item(&toggle_statusbar)
        .build()?;

    let window_sub = SubmenuBuilder::new(app, "Window")
        .item(&PredefinedMenuItem::minimize(app, None)?)
        .item(&PredefinedMenuItem::maximize(app, None)?)
        .build()?;

    let about = MenuItemBuilder::new("About Sultan Clip")
        .id("help.about")
        .build(app)?;
    let docs = MenuItemBuilder::new("Documentation")
        .id("help.docs")
        .build(app)?;
    let help_sub = SubmenuBuilder::new(app, "Help")
        .item(&about)
        .item(&docs)
        .build()?;

    #[cfg(target_os = "macos")]
    {
        window_sub.set_as_windows_menu_for_nsapp()?;
        help_sub.set_as_help_menu_for_nsapp()?;
    }

    let menu = MenuBuilder::new(app)
        .item(&file_sub)
        .item(&edit_sub)
        .item(&view_sub)
        .item(&window_sub)
        .item(&help_sub)
        .build()?;
    app.set_menu(menu)?;

    app.on_menu_event(|app_handle, event| {
        let _ = app_handle.emit(
            "menu-action",
            MenuAction {
                item_id: event.id().0.clone(),
            },
        );
    });

    Ok(())
}
