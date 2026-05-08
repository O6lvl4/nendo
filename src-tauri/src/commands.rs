use crate::glb::GlbFile;
use serde_json::Value;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::State;

pub struct AppState {
    pub vrm_path: PathBuf,
    pub glb: GlbFile,
}

pub type AppStateMutex = Mutex<Option<AppState>>;

fn presets_path(vrm_path: &PathBuf) -> PathBuf {
    vrm_path.with_extension("presets.json")
}

fn vrm_root(json: &Value) -> &Value {
    if json["extensions"]["VRMC_vrm"].is_object() {
        &json["extensions"]["VRMC_vrm"]
    } else {
        &json["extensions"]["VRM"]
    }
}

fn is_v1(json: &Value) -> bool {
    json["extensions"]["VRMC_vrm"].is_object()
}

#[tauri::command]
pub fn open_vrm(path: String, state: State<'_, AppStateMutex>) -> Result<Value, String> {
    let p = PathBuf::from(&path);
    let glb = GlbFile::load(&p)?;
    let summary = build_summary(&glb.json);
    *state.lock().unwrap() = Some(AppState { vrm_path: p, glb });
    Ok(summary)
}

#[tauri::command]
pub fn get_vrm_asset_url(
    state: State<'_, AppStateMutex>,
) -> Result<String, String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    let abs = st.vrm_path.canonicalize().map_err(|e| e.to_string())?;
    Ok(abs.to_string_lossy().to_string())
}

#[tauri::command]
pub fn get_summary(state: State<'_, AppStateMutex>) -> Result<Value, String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    Ok(build_summary(&st.glb.json))
}

#[tauri::command]
pub fn get_meta(state: State<'_, AppStateMutex>) -> Result<Value, String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    let root = vrm_root(&st.glb.json);
    Ok(root["meta"].clone())
}

#[tauri::command]
pub fn set_meta(data: Value, state: State<'_, AppStateMutex>) -> Result<(), String> {
    let mut guard = state.lock().unwrap();
    let st = guard.as_mut().ok_or("no VRM loaded")?;
    let key = if is_v1(&st.glb.json) {
        "VRMC_vrm"
    } else {
        "VRM"
    };
    st.glb.json["extensions"][key]["meta"] = data;
    st.glb.save(&st.vrm_path)
}

#[tauri::command]
pub fn get_presets(state: State<'_, AppStateMutex>) -> Result<Value, String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    let p = presets_path(&st.vrm_path);
    if p.exists() {
        let s = std::fs::read_to_string(&p).map_err(|e| e.to_string())?;
        serde_json::from_str(&s).map_err(|e| e.to_string())
    } else {
        Ok(serde_json::json!([]))
    }
}

#[tauri::command]
pub fn save_preset(preset: Value, state: State<'_, AppStateMutex>) -> Result<(), String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    let p = presets_path(&st.vrm_path);

    let mut data: Vec<Value> = if p.exists() {
        let s = std::fs::read_to_string(&p).unwrap_or_else(|_| "[]".into());
        serde_json::from_str(&s).unwrap_or_default()
    } else {
        Vec::new()
    };

    let name = preset["name"].as_str().unwrap_or("");
    data.retain(|d| d["name"].as_str() != Some(name));
    data.push(preset);

    let json = serde_json::to_string_pretty(&data).map_err(|e| e.to_string())?;
    std::fs::write(&p, json).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn delete_preset(name: String, state: State<'_, AppStateMutex>) -> Result<(), String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    let p = presets_path(&st.vrm_path);

    if p.exists() {
        let s = std::fs::read_to_string(&p).unwrap_or_else(|_| "[]".into());
        let mut data: Vec<Value> = serde_json::from_str(&s).unwrap_or_default();
        data.retain(|d| d["name"].as_str() != Some(&name));
        let json = serde_json::to_string_pretty(&data).map_err(|e| e.to_string())?;
        std::fs::write(&p, json).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn get_texture(idx: usize, state: State<'_, AppStateMutex>) -> Result<Vec<u8>, String> {
    let guard = state.lock().unwrap();
    let st = guard.as_ref().ok_or("no VRM loaded")?;
    st.glb.extract_image(idx)
}

#[tauri::command]
pub fn replace_texture(
    idx: usize,
    data: Vec<u8>,
    state: State<'_, AppStateMutex>,
) -> Result<(), String> {
    let mut guard = state.lock().unwrap();
    let st = guard.as_mut().ok_or("no VRM loaded")?;
    st.glb.replace_image(idx, &data)?;
    st.glb.save(&st.vrm_path)
}

#[tauri::command]
pub fn save_customization(data: Value, state: State<'_, AppStateMutex>) -> Result<(), String> {
    let mut guard = state.lock().unwrap();
    let st = guard.as_mut().ok_or("no VRM loaded")?;

    if let Some(weights) = data["weights"].as_object() {
        for (mesh_idx_str, w_list) in weights {
            let mesh_idx: usize = mesh_idx_str.parse().unwrap_or(usize::MAX);
            if let Some(mesh) = st.glb.json["meshes"].get_mut(mesh_idx) {
                mesh["weights"] = w_list.clone();
            }
        }
    }

    if let Some(materials) = data["materials"].as_object() {
        for (mat_idx_str, props) in materials {
            let mat_idx: usize = mat_idx_str.parse().unwrap_or(usize::MAX);
            if let Some(mat) = st.glb.json["materials"].get_mut(mat_idx) {
                if let Some(bc) = props.get("baseColor") {
                    mat["pbrMetallicRoughness"]["baseColorFactor"] = bc.clone();
                }
            }
        }
    }

    st.glb.save(&st.vrm_path)
}

fn build_summary(json: &Value) -> Value {
    let root = vrm_root(json);
    let v1 = is_v1(json);

    let title = if v1 {
        root["meta"]["name"].as_str().unwrap_or("")
    } else {
        root["meta"]["title"].as_str().unwrap_or("")
    };

    let author = if v1 {
        root["meta"]["authors"].clone()
    } else {
        Value::String(root["meta"]["author"].as_str().unwrap_or("").into())
    };

    let count = |key: &str| json[key].as_array().map(|a| a.len()).unwrap_or(0);

    serde_json::json!({
        "version": if v1 { "1.0" } else { "0.x" },
        "title": title,
        "author": author,
        "meshes": count("meshes"),
        "nodes": count("nodes"),
        "materials": count("materials"),
        "textures": count("textures"),
        "images": count("images"),
    })
}
