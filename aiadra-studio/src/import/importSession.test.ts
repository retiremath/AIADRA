import { describe, expect, it, vi } from 'vitest'
import { createImportSession } from './importSession'
import type { ImportedMesh } from './normalize'

function meshes(): ImportedMesh[] {
  return [{ name: 'm', position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]) }]
}

function sink() {
  return { addImported: vi.fn(), removeImported: vi.fn() }
}

describe('createImportSession — B3 remove-during-loading race', () => {
  it('adds to the viewport on the normal begin → complete path', () => {
    const s = sink()
    const session = createImportSession(s)
    session.begin('a')
    expect(session.complete('a', meshes())).toBe(true)
    expect(s.addImported).toHaveBeenCalledTimes(1)
    expect(s.addImported).toHaveBeenCalledWith('a', expect.anything())
  })

  it('DROPS a result whose row was removed while still loading (no orphan)', () => {
    const s = sink()
    const session = createImportSession(s)
    session.begin('a')
    session.remove('a') // user clicks Remove before the parse resolves
    const applied = session.complete('a', meshes()) // parse resolves afterwards
    expect(applied).toBe(false)
    expect(s.addImported).not.toHaveBeenCalled() // <-- the B3 invariant
    expect(s.removeImported).toHaveBeenCalledWith('a') // remove still told the viewport to drop
  })

  it('removes an already-added (ready) import normally', () => {
    const s = sink()
    const session = createImportSession(s)
    session.begin('a')
    session.complete('a', meshes())
    session.remove('a')
    expect(s.addImported).toHaveBeenCalledTimes(1)
    expect(s.removeImported).toHaveBeenCalledTimes(1)
  })

  it('does not tombstone an id removed when it is not in flight (no leak)', () => {
    const s = sink()
    const session = createImportSession(s)
    session.begin('a')
    session.complete('a', meshes()) // a is now settled, not in flight
    session.remove('a') // normal remove
    // A brand-new import reusing nothing of 'a' must still apply.
    session.begin('b')
    expect(session.complete('b', meshes())).toBe(true)
    expect(s.addImported).toHaveBeenCalledTimes(2)
  })

  it('clears lifecycle state on error so the id is not stuck cancelled', () => {
    const s = sink()
    const session = createImportSession(s)
    session.begin('a')
    session.settleError('a')
    // 'a' was never tombstoned; a later (hypothetical) complete would still apply.
    session.begin('a')
    expect(session.complete('a', meshes())).toBe(true)
    expect(s.addImported).toHaveBeenCalledTimes(1)
  })
})
