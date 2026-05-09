# nendo almide版 ロードマップ

## 完了

- [x] GLBバイナリパーサー (glb.almd) — load/save/extract_image
- [x] VRMモデル層 (vrm.almd) — meta, humanoid, expressions, summary
- [x] CLI: inspect, validate, tree, dump
- [x] almide本体のバグ修正 (PR #251)
  - let mut自動昇格 (Bytes/Vec/HashMap)
  - err() in match arm → Ty::Never + return Err
  - モジュール修飾レコードリテラル
  - FileStat構造体定義
  - guard-else Ok()ラップ

## 次: obsid描画

lumen (数学) + obsid (WebGL) で VRM を WASM 上で描画する。

### Phase 1: 静的メッシュ表示
- [ ] glTFアクセサーデコード — accessor → Float32/Uint16 配列
- [ ] 頂点バッファ構築 — position + normal + color を obsid 44byte/vertex 形式に変換
- [ ] インデックスバッファ構築 — u16 LE
- [ ] obsid.upload_mesh() でGPUに送信
- [ ] obsid.orbit カメラ + Phong ライティングで表示
- [ ] `almide build --target wasm` で .wasm 出力、ブラウザで確認

### Phase 2: マテリアル
- [ ] テクスチャ抽出 → obsid.upload_texture()
- [ ] マテリアルカラー → obsid.set_mesh_material()
- [ ] 複数メッシュ対応（Body, Hair, Clothing 等）

### Phase 3: ボーン・アニメーション
- [ ] スキンデータ読み込み（joints + inverseBindMatrices）
- [ ] ボーンウェイト適用（CPU頂点変換 or シェーダー）
- [ ] アイドルアニメーション（呼吸・まばたき）

### Phase 4: VRM固有
- [ ] SpringBone物理（Verlet積分）
- [ ] Expression/BlendShape（モーフターゲット）
- [ ] MToonシェーダー相当（obsidカスタムシェーダー or 近似）

## 依存関係

- **lumen** (almide/lumen) — vec3, mat4, color
- **obsid** (almide/obsid) — WebGL描画、orbit camera、メッシュ管理
- **almide 0.15.6+** — PR #251 の修正が必要
