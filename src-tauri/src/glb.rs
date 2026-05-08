use serde_json::Value;
use std::path::Path;

const GLB_MAGIC: u32 = 0x46546C67;
const CHUNK_JSON: u32 = 0x4E4F534A;
const CHUNK_BIN: u32 = 0x004E4942;

#[derive(Clone)]
pub struct GlbFile {
    pub json: Value,
    pub bin: Vec<u8>,
}

impl GlbFile {
    pub fn load(path: &Path) -> Result<Self, String> {
        let data = std::fs::read(path).map_err(|e| format!("read: {e}"))?;
        Self::parse(&data)
    }

    pub fn parse(data: &[u8]) -> Result<Self, String> {
        if data.len() < 12 {
            return Err("too small".into());
        }
        let magic = u32::from_le_bytes(data[0..4].try_into().unwrap());
        if magic != GLB_MAGIC {
            return Err(format!("not GLB: {magic:#x}"));
        }
        let total = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;

        let mut offset = 12usize;
        let mut json_val: Option<Value> = None;
        let mut bin_data: Vec<u8> = Vec::new();

        while offset + 8 <= total.min(data.len()) {
            let chunk_len = u32::from_le_bytes(data[offset..offset + 4].try_into().unwrap()) as usize;
            let chunk_type = u32::from_le_bytes(data[offset + 4..offset + 8].try_into().unwrap());
            offset += 8;
            let end = (offset + chunk_len).min(data.len());

            match chunk_type {
                CHUNK_JSON => {
                    json_val = Some(serde_json::from_slice(&data[offset..end]).map_err(|e| format!("json: {e}"))?);
                }
                CHUNK_BIN => {
                    bin_data = data[offset..end].to_vec();
                }
                _ => {}
            }
            offset = end;
        }

        Ok(Self {
            json: json_val.ok_or("no JSON chunk")?,
            bin: bin_data,
        })
    }

    pub fn save(&self, path: &Path) -> Result<(), String> {
        let json_bytes = serde_json::to_vec(&self.json).map_err(|e| format!("json: {e}"))?;
        let json_pad = (4 - json_bytes.len() % 4) % 4;
        let json_padded_len = json_bytes.len() + json_pad;

        let has_bin = !self.bin.is_empty();
        let bin_pad = if has_bin { (4 - self.bin.len() % 4) % 4 } else { 0 };

        let mut total = 12 + 8 + json_padded_len;
        if has_bin {
            total += 8 + self.bin.len() + bin_pad;
        }

        let mut out = Vec::with_capacity(total);
        out.extend_from_slice(&GLB_MAGIC.to_le_bytes());
        out.extend_from_slice(&2u32.to_le_bytes());
        out.extend_from_slice(&(total as u32).to_le_bytes());

        out.extend_from_slice(&(json_padded_len as u32).to_le_bytes());
        out.extend_from_slice(&CHUNK_JSON.to_le_bytes());
        out.extend_from_slice(&json_bytes);
        out.extend(std::iter::repeat(b' ').take(json_pad));

        if has_bin {
            out.extend_from_slice(&((self.bin.len() + bin_pad) as u32).to_le_bytes());
            out.extend_from_slice(&CHUNK_BIN.to_le_bytes());
            out.extend_from_slice(&self.bin);
            out.extend(std::iter::repeat(0u8).take(bin_pad));
        }

        std::fs::write(path, &out).map_err(|e| format!("write: {e}"))
    }

    pub fn extract_image(&self, idx: usize) -> Result<Vec<u8>, String> {
        let images = self.json["images"].as_array().ok_or("no images")?;
        let img = images.get(idx).ok_or("image index out of range")?;
        let bv_idx = img["bufferView"].as_u64().ok_or("no bufferView")? as usize;
        let bvs = self.json["bufferViews"].as_array().ok_or("no bufferViews")?;
        let bv = bvs.get(bv_idx).ok_or("bufferView out of range")?;
        let offset = bv["byteOffset"].as_u64().unwrap_or(0) as usize;
        let length = bv["byteLength"].as_u64().ok_or("no byteLength")? as usize;
        Ok(self.bin[offset..offset + length].to_vec())
    }

    pub fn replace_image(&mut self, idx: usize, new_data: &[u8]) -> Result<(), String> {
        let bv_idx = self.json["images"][idx]["bufferView"]
            .as_u64()
            .ok_or("invalid image")? as usize;

        let old_offset = self.json["bufferViews"][bv_idx]["byteOffset"]
            .as_u64()
            .unwrap_or(0) as usize;
        let old_length = self.json["bufferViews"][bv_idx]["byteLength"]
            .as_u64()
            .ok_or("no byteLength")? as usize;
        let size_diff = new_data.len() as i64 - old_length as i64;

        let mut new_bin = self.bin[..old_offset].to_vec();
        new_bin.extend_from_slice(new_data);
        new_bin.extend_from_slice(&self.bin[old_offset + old_length..]);
        self.bin = new_bin;

        self.json["bufferViews"][bv_idx]["byteLength"] = serde_json::json!(new_data.len());

        if let Some(bvs) = self.json["bufferViews"].as_array_mut() {
            for (i, bv) in bvs.iter_mut().enumerate() {
                if i == bv_idx {
                    continue;
                }
                let off = bv["byteOffset"].as_u64().unwrap_or(0) as i64;
                if off > old_offset as i64 {
                    bv["byteOffset"] = serde_json::json!((off + size_diff) as u64);
                }
            }
        }

        if let Some(buffers) = self.json["buffers"].as_array_mut() {
            if let Some(buf) = buffers.first_mut() {
                buf["byteLength"] = serde_json::json!(self.bin.len());
            }
        }

        Ok(())
    }
}
