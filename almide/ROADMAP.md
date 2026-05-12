# nendo almide — VRM Rendering Roadmap

> Goal: three.js を完全に排除し、almide + lumen + obsid で VRM をブラウザレンダリングする。

## 現状

```
✅ glb.almd    — GLB バイナリパース (chunk parse, save, image extract)
✅ vrm.almd    — VRM メタデータ (version detect, meta, bones, expressions)
✅ main.almd   — CLI (inspect, validate, tree, dump)
✅ web.almd    — WASM API (inspect, validate, get_json)
```

## 依存スタック

```
nendo (almide)
  ├── dubhlux/lumen   vec3, mat4, color — ✅ exists
  ├── dubhlux/obsid   WebGL renderer — ✅ exists
  └── almide stdlib   bytes, json — ✅ exists
```

## 足りないもの

### Phase 0: 依存の確認と接続
- [ ] almide.toml に lumen, obsid を依存追加
- [ ] `almide build --target wasm` で nendo + lumen + obsid が結合ビルドできることを確認
- [ ] obsid の host JS (WebGL bootstrap) が nendo の WASM を正しくロードできることを確認

### Phase 1: glTF accessor → obsid vertex buffer (MVP)
- [ ] `accessor.almd` — glTF accessor/bufferView 読み出し
  - accessor → (componentType, count, type, byteOffset, bufferView)
  - bufferView → (byteOffset, byteLength, byteStride, target)
  - Float32/UInt16 array 読み出し (bytes モジュール使用)
- [ ] `mesh.almd` — glTF mesh → obsid vertex data 変換
  - POSITION (vec3 float32) → obsid pos[3]
  - NORMAL (vec3 float32) → obsid norm[3]
  - UV なし → material base color を vertex color に
  - INDEX (uint16) → obsid index buffer
  - 出力: `(vert_bytes: Bytes, idx_bytes: Bytes, vert_count: Int, idx_count: Int)`
- [ ] `render.almd` — obsid で描画
  - `obsid.create_mesh(id)` + `obsid.upload_mesh(id, vert_ptr, vert_count, idx_ptr, idx_count)`
  - orbit camera (obsid built-in)
  - directional light + ambient
- [ ] `web/viewer.html` — obsid host JS + nendo WASM
  - D&D で VRM ファイルを受け取り → WASM に渡す → obsid でレンダリング
  - three.js 依存ゼロ

### Phase 2: Material
- [ ] `material.almd` — glTF material → obsid material 変換
  - baseColorFactor → `obsid.set_mesh_material()` の color
  - baseColorTexture → Phase 2+ (obsid に UV サポートが必要)
  - metallic/roughness → shininess 近似
- [ ] obsid: テクスチャ座標 (UV) サポート追加
  - vertex format 拡張: pos[3] + norm[3] + color[3] + uv[2] = 44 bytes
  - fragment shader に texcoord varying 追加
  - `obsid.upload_texture()` + `obsid.set_mesh_texture()`

### Phase 3: Skeleton + Skinning
- [ ] `skeleton.almd` — bone hierarchy
  - glTF skin → bone list (inverseBindMatrices, joints)
  - node tree → world transform per bone (lumen.mat4.mul chain)
  - rest pose → bind pose matrices
- [ ] `skin.almd` — CPU skinning
  - JOINTS_0 (uvec4) + WEIGHTS_0 (vec4) accessor 読み出し
  - per-vertex: `pos = sum(weight[i] * boneMatrix[joint[i]] * pos)`
  - lumen.mat4 で行列計算
  - obsid.upload_mesh で毎フレーム再アップロード
- [ ] animation (基礎)
  - glTF animation → channel (node, path, sampler)
  - sampler → keyframe interpolation (LINEAR のみ)
  - bone transform 更新 → skinning → render

### Phase 4: Morph Target (BlendShape)
- [ ] `morph.almd` — morph target blending
  - glTF morph targets → delta position/normal arrays
  - `weight * delta` を base mesh に加算 (CPU)
  - VRM expressions → morph target weight マッピング
- [ ] expression UI
  - WASM export: `set_expression(name: String, weight: Float)`
  - host JS からスライダー操作

## ブロッカー (almide compiler / stdlib)

| 項目 | 状態 | 影響 |
|------|------|------|
| `bytes.read_f32_le` | ✅ stdlib にある | accessor float32 読み出し |
| `bytes.read_u16_le` | ✅ stdlib にある | index buffer 読み出し |
| WASM multi-module | ✅ almide.toml deps で動く | nendo + lumen + obsid 結合 |
| `@extern(wasm)` | ✅ obsid で実績あり | WebGL 呼び出し |
| WASM linear memory 直接書き込み | ❓ 要確認 | vertex buffer をメモリに書いて ptr を obsid に渡す |
| WASM memory export | ❓ 要確認 | host JS が WASM memory を read する |

## 成功判定

Phase 1 完了時: ブラウザで VRM ファイルをドラッグ&ドロップすると、three.js なしで 3D メッシュが表示される。orbit camera で回転可能。
