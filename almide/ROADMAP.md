# nendo — almide VRM rendering engine

> almide + obsid で three.js なしに VRM をブラウザ表示・操作する

## Architecture

```
almide (.almd) → WASM → obsid (WebGL host) → browser

nendo (almide)
  ├── dubhlux/lumen   — vec3, mat4, color (数学)
  ├── dubhlux/obsid   — WebGL renderer (描画)
  └── almide stdlib   — bytes, json (基盤)
```

## Done

- [x] GLB binary parser (chunk parse, JSON + binary extraction)
- [x] Mesh loading (all primitives, byteStride, u16/u32 index conversion)
- [x] Textures (TEXCOORD_0 UV, PNG/JPEG decode via obsid, material→texture→image binding)
- [x] CPU skinning (node hierarchy, joint matrices, 4-bone weighted blending)
- [x] MToon toon shading (almide-defined GLSL, _Color, _ShadeColor, rim light)
- [x] Arena memory management (bytes.heap_save/restore per primitive)
- [x] Custom shader API (obsid.create_shader_program, set_mesh_shader)
- [x] VRM 0.x detection + material properties
- [x] Orbit camera + pointer/wheel controls

## Phase 1: Animation
- [ ] glTF animation channels + samplers
- [ ] Keyframe interpolation (linear, step, cubic spline)
- [ ] Skeletal animation (bone transforms update per frame)
- [ ] Animation mixer (play, pause, crossfade)
- [ ] Morph targets / blend shapes (delta position/normal)
- [ ] Per-frame mesh re-upload (CPU skinning + morph → obsid)

## Phase 2: VRM Features
- [ ] VRM expressions (blend shape groups → morph target weights)
- [ ] VRM look-at (eye bone rotation tracking)
- [ ] VRM spring bones (hair/clothing secondary physics)
- [ ] VRM 1.0 VRMC_vrm / VRMC_materials_mtoon
- [ ] Expression API: `set_expression(name, weight)` WASM export

## Phase 3: Rendering Quality
- [ ] MToon outline pass (inverted hull, separate draw call)
- [ ] MToon emission / matcap / shade texture
- [ ] Shadow mapping (directional light)
- [ ] Alpha blending + transparency sorting
- [ ] Post-processing (bloom, SSAO, screen-space outline)

## Phase 4: Engine
- [ ] Scene graph (node hierarchy with world transforms)
- [ ] GPU skinning (bone matrices as texture)
- [ ] Instanced rendering
- [ ] Frustum culling
- [ ] LOD (level of detail)

## Phase 5: Platform
- [ ] dlmalloc for WASM (proper allocator)
- [ ] JSON glTF (non-binary) support
- [ ] WebXR (VR/AR)
- [ ] Mobile touch
- [ ] obsid upstream (eliminate cache hack)

## Known Compiler Issues
| Issue | Status | Impact |
|-------|--------|--------|
| JSON array >64 elements | **fixed** | VRM with many accessors |
| bytes.heap_save/restore | **added** | arena memory pattern |
| var-in-if WASM codegen | **workaround** | skin blending uses let-only |
| @extern name collision | **fixed** | webgl.create_program vs obsid |
| Complex fn return value | open | non-blocking (display works) |
