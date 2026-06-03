// B2 evidence (arc 20260603-1): prove the occt-import-js WASM pipeline parses a
// real STEP file using `wasmBinary` (bytes provided, NO fetch) — the file://-safe
// delivery path. Run: `node scripts/step-smoke.cjs`.
const path = require('node:path')
const fs = require('node:fs')
const occtimportjs = require('occt-import-js')

const pkg = path.dirname(require.resolve('occt-import-js'))
const wasm = fs.readFileSync(path.join(pkg, 'occt-import-js.wasm'))
const stepPath = path.join(pkg, '..', 'test', 'testfiles', 'cax-if', 'as1-oc-214.stp')
const step = fs.readFileSync(stepPath)

occtimportjs({ wasmBinary: wasm })
  .then((occt) => {
    const r = occt.ReadStepFile(new Uint8Array(step), null)
    const meshes = r.meshes || []
    const tris = meshes.reduce((n, m) => n + (m.index ? m.index.array.length / 3 : 0), 0)
    const faces = meshes.reduce((n, m) => n + (m.brep_faces ? m.brep_faces.length : 0), 0)
    console.log(`wasmBinary init OK | success: ${r.success} | meshes: ${meshes.length} | triangles: ${tris} | brep_faces: ${faces}`)
    console.log(`mesh0 position: ${!!meshes[0]?.attributes?.position} | normal: ${!!meshes[0]?.attributes?.normal} | index: ${!!meshes[0]?.index}`)
    if (!r.success || meshes.length === 0) process.exit(2)
  })
  .catch((e) => {
    console.error('SMOKE FAILED:', e)
    process.exit(1)
  })
