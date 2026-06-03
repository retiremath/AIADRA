import { describe, expect, it } from 'vitest'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { normalizeMeshes } from './normalize'

/** Build a minimal binary STL (80-byte header + uint32 count + 50 bytes/triangle). */
function binaryStl(triangles: number[][][]): ArrayBuffer {
  const buf = new ArrayBuffer(84 + triangles.length * 50)
  const dv = new DataView(buf)
  dv.setUint32(80, triangles.length, true)
  let off = 84
  for (const tri of triangles) {
    off += 12 // face normal (0,0,0) — STLLoader derives per-vertex normals
    for (const v of tri) {
      dv.setFloat32(off, v[0], true)
      dv.setFloat32(off + 4, v[1], true)
      dv.setFloat32(off + 8, v[2], true)
      off += 12
    }
    off += 2 // attribute byte count
  }
  return buf
}

/** End-to-end of the mandatory STL lane: the REAL three.js STLLoader the worker
 *  uses, fed through the B1 normalize gate, yields a valid reference mesh. */
describe('STL lane — real STLLoader through the B1 gate', () => {
  it('parses a binary STL and passes normalization', () => {
    const geo = new STLLoader().parse(
      binaryStl([
        [[0, 0, 0], [10, 0, 0], [0, 10, 0]],
        [[0, 0, 0], [0, 10, 0], [0, 0, 10]],
      ]),
    )
    const pos = geo.getAttribute('position').array
    const nrm = geo.getAttribute('normal')
    const position = pos instanceof Float32Array ? pos : Float32Array.from(pos)
    const normal = nrm ? (nrm.array instanceof Float32Array ? nrm.array : Float32Array.from(nrm.array)) : undefined

    const meshes = normalizeMeshes([{ name: 'imported mesh', position, normal }])
    expect(meshes).toHaveLength(1)
    expect(meshes[0].position.length).toBe(18) // 2 triangles × 3 verts × 3
    expect(meshes[0].normal?.length).toBe(18)
  })
})
