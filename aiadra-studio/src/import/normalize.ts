/**
 * Import-lane output normalization + safety gate (Codex1 B1, arc 20260603-1).
 *
 * The parse Web Worker returns geometry built from UNTRUSTED external bytes. A
 * worker keeps that parse off the UI thread and off the privileged side, but it
 * can still hand back malformed or enormous arrays that would hang the renderer,
 * exhaust memory, or feed invalid buffers into three.js. This module is the
 * renderer-side "reject loudly at the boundary" gate: nothing reaches
 * `Viewport.addImported(...)` until it passes here.
 *
 * This is NOT Product-Truth validation — imported geometry is reference-only and
 * never becomes Truth (ADR/0032 D5). It is purely defensive shaping of untrusted
 * geometry bytes. Pure + synchronous so it is unit-testable without a worker.
 */

/** A validated, render-ready mesh from the import lane. Reference geometry only. */
export type ImportedMesh = {
  name: string
  /** Flat XYZ triplets; `length % 3 === 0`. */
  position: Float32Array
  /** Per-vertex normals (same length as `position`) or absent. */
  normal?: Float32Array
  /** Triangle indices (`length % 3 === 0`, all in `[0, vertexCount)`) or absent. */
  index?: Uint32Array
  /**
   * occt-import-js BREP-face → index ranges, retained verbatim. PROVISIONAL
   * render metadata ONLY (Codex1 N2): these are NOT topology IDs or selection
   * handles, and 1b exposes no selection over them. Topology-preserved selection
   * (ADR/0032 D4/D8) waits for milestone 2's occt-import-js vs opencascade.js
   * stable-ID comparison. The name is deliberately ugly so it cannot be mistaken
   * for a supported selection surface.
   */
  brepFaceRangesUnused?: { first: number; last: number }[]
}

export type ImportCaps = {
  /** Max vertices summed across all meshes in one imported file. */
  maxVertices: number
  /** Max triangles summed across all meshes in one imported file. */
  maxTriangles: number
}

/** Conservative 1b caps; a hung/huge import is rejected, not rendered. */
export const DEFAULT_CAPS: ImportCaps = { maxVertices: 5_000_000, maxTriangles: 4_000_000 }

/** Thrown by the import lane on any boundary-validation or resource failure. */
export class ImportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ImportError'
  }
}

function isFloat32(v: unknown): v is Float32Array {
  return v instanceof Float32Array
}
function isUint32(v: unknown): v is Uint32Array {
  return v instanceof Uint32Array
}

function allFinite(a: Float32Array): boolean {
  for (let i = 0; i < a.length; i++) {
    if (!Number.isFinite(a[i])) return false
  }
  return true
}

function normalizeFaceRanges(raw: unknown, indexLen: number): { first: number; last: number }[] | undefined {
  if (!Array.isArray(raw)) return undefined
  const out: { first: number; last: number }[] = []
  for (const r of raw) {
    if (!r || typeof r !== 'object') continue
    const first = (r as Record<string, unknown>).first
    const last = (r as Record<string, unknown>).last
    if (
      typeof first === 'number' &&
      typeof last === 'number' &&
      Number.isInteger(first) &&
      Number.isInteger(last) &&
      first >= 0 &&
      last >= first &&
      last <= indexLen
    ) {
      out.push({ first, last })
    }
  }
  return out.length ? out : undefined
}

/**
 * Validate + normalize the worker's raw mesh list into render-ready `ImportedMesh`es,
 * enforcing every B1 invariant. Throws `ImportError` on the first violation.
 *
 * @param rawMeshes the `meshes` field of a worker `ok` message (untrusted shape)
 */
export function normalizeMeshes(rawMeshes: unknown, caps: ImportCaps = DEFAULT_CAPS): ImportedMesh[] {
  if (!Array.isArray(rawMeshes) || rawMeshes.length === 0) {
    throw new ImportError('import produced no geometry')
  }

  const meshes: ImportedMesh[] = []
  let totalVertices = 0
  let totalTriangles = 0

  for (let m = 0; m < rawMeshes.length; m++) {
    const raw = rawMeshes[m] as Record<string, unknown> | null
    if (!raw || typeof raw !== 'object') {
      throw new ImportError(`mesh ${m}: not an object`)
    }

    const position = raw.position
    if (!isFloat32(position) || position.length === 0 || position.length % 3 !== 0) {
      throw new ImportError(`mesh ${m}: position must be a non-empty Float32Array with length % 3 === 0`)
    }
    if (!allFinite(position)) {
      throw new ImportError(`mesh ${m}: position contains non-finite values`)
    }
    const vertexCount = position.length / 3

    let normal: Float32Array | undefined
    if (raw.normal !== undefined && raw.normal !== null) {
      if (!isFloat32(raw.normal) || raw.normal.length !== position.length) {
        throw new ImportError(`mesh ${m}: normal must match position length`)
      }
      if (!allFinite(raw.normal)) {
        throw new ImportError(`mesh ${m}: normal contains non-finite values`)
      }
      normal = raw.normal
    }

    let index: Uint32Array | undefined
    let triangleCount: number
    if (raw.index !== undefined && raw.index !== null) {
      if (!isUint32(raw.index) || raw.index.length === 0 || raw.index.length % 3 !== 0) {
        throw new ImportError(`mesh ${m}: index must be a Uint32Array with length % 3 === 0`)
      }
      for (let i = 0; i < raw.index.length; i++) {
        if (raw.index[i] >= vertexCount) {
          throw new ImportError(`mesh ${m}: index ${i} (${raw.index[i]}) out of range (vertices=${vertexCount})`)
        }
      }
      index = raw.index
      triangleCount = index.length / 3
    } else {
      // Non-indexed: every 3 vertices is a triangle.
      triangleCount = vertexCount / 3
    }

    totalVertices += vertexCount
    totalTriangles += triangleCount
    if (totalVertices > caps.maxVertices) {
      throw new ImportError(`import exceeds vertex cap (${totalVertices} > ${caps.maxVertices})`)
    }
    if (totalTriangles > caps.maxTriangles) {
      throw new ImportError(`import exceeds triangle cap (${totalTriangles} > ${caps.maxTriangles})`)
    }

    meshes.push({
      name: typeof raw.name === 'string' && raw.name ? raw.name : `solid ${m + 1}`,
      position,
      normal,
      index,
      brepFaceRangesUnused: normalizeFaceRanges(raw.brepFaceRangesUnused, index ? index.length : position.length / 3),
    })
  }

  return meshes
}
