#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod glb;

use commands::AppStateMutex;
use std::sync::Mutex;

fn main() {
    // Pre-load VRM from CLI argument if provided
    let initial_state: AppStateMutex = {
        let args: Vec<String> = std::env::args().collect();
        if let Some(path) = args.get(1) {
            let p = std::path::PathBuf::from(path);
            match glb::GlbFile::load(&p) {
                Ok(glb) => {
                    eprintln!("Loaded: {}", p.display());
                    Mutex::new(Some(commands::AppState { vrm_path: p, glb }))
                }
                Err(e) => {
                    eprintln!("Failed to load {}: {e}", p.display());
                    Mutex::new(None)
                }
            }
        } else {
            Mutex::new(None)
        }
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(initial_state)
        .invoke_handler(tauri::generate_handler![
            commands::open_vrm,
            commands::get_vrm_asset_url,
            commands::get_summary,
            commands::get_meta,
            commands::set_meta,
            commands::get_presets,
            commands::save_preset,
            commands::delete_preset,
            commands::get_texture,
            commands::replace_texture,
            commands::save_customization,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
