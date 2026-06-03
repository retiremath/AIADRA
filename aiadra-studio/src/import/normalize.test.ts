import { describe, expect, it } from 'vitest'
import { ImportError, normalizeMeshes } from './normalize'

/** One valid non-indexed triangle (3 verts) with matching normals. */
function triMesh(extra: Record<string, unknown> = {}) {
  return {
    name: 'm',
    position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    normal: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    ...extra,
  }
}

describe('normalizeMeshes — B1 output validation gate', () => {
  it('accepts a valid non-indexed mesh', () => {
    const out = normalizeMeshes([triMesh()])
    expect(out).toHaveLength(1)
    expect(out[0].position.length).toBe(9)
    expect(out[0].normal?.length).toBe(9)
    expect(out[0].index).toBeUndefined()
  })

  it('accepts a valid indexed mesh and passes face ranges through', () => {
    const out = normalizeMeshes([
      {
        position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 0]),
        index: new Uint32Array([0, 1, 2, 1, 3, 2]),
        brepFaceRangesUnused: [{ first: 0, last: 6 }],
      },
    ])
    expect(out[0].index?.length).toBe(6)
    expect(out[0].brepFaceRangesUnused).toEqual([{ first: 0, last: 6 }])
  })

  it('rejects an empty mesh list', () => {
    expect(() => normalizeMeshes([])).toThrow(ImportError)
  })

  it('rejects a non-array payload', () => {
    expect(() => normalizeMeshes({ nope: true })).toThrow(ImportError)
  })

  it('rejects a position that is not a Float32Array', () => {
    expect(() => normalizeMeshes([{ position: [0, 0, 0] }])).toThrow(/Float32Array/)
  })

  it('rejects a position length not divisible by 3', () => {
    expect(() => normalizeMeshes([{ position: new Float32Array([0, 0, 0, 1]) }])).toThrow(/% 3/)
  })

  it('rejects non-finite position values', () => {
    expect(() => normalizeMeshes([{ position: new Float32Array([0, 0, NaN]) }])).toThrow(/non-finite/)
  })

  it('rejects a normal whose length does not match position', () => {
    expect(() => normalizeMeshes([triMesh({ normal: new Float32Array([0, 0, 1]) })])).toThrow(/normal/)
  })

  it('rejects an index that is not a Uint32Array', () => {
    expect(() => normalizeMeshes([triMesh({ index: [0, 1, 2] })])).toThrow(/Uint32Array/)
  })

  it('rejects an index length not divisible by 3', () => {
    expect(() => normalizeMeshes([triMesh({ index: new Uint32Array([0, 1, 2, 0]) })])).toThrow(/% 3/)
  })

  it('rejects an out-of-range index', () => {
    expect(() => normalizeMeshes([triMesh({ index: new Uint32Array([0, 1, 9]) })])).toThrow(/out of range/)
  })

  it('enforces the vertex cap', () => {
    expect(() => normalizeMeshes([triMesh()], { maxVertices: 2, maxTriangles: 10 })).toThrow(/vertex cap/)
  })

  it('enforces the triangle cap', () => {
    expect(() => normalizeMeshes([triMesh()], { maxVertices: 100, maxTriangles: 0 })).toThrow(/triangle cap/)
  })

  it('drops malformed face ranges rather than trusting them', () => {
    const out = normalizeMeshes([triMesh({ brepFaceRangesUnused: [{ first: 'x', last: 3 }, { first: 0, last: 999 }] })])
    expect(out[0].brepFaceRangesUnused).toBeUndefined()
  })
})
