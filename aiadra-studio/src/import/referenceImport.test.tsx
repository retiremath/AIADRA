/**
 * Codex2 B2 — the reference-import lifecycle policy: references are
 * MODELING-SCOPED. `clearAll()` runs as modeling closes (before viewport
 * teardown); ready rows drop their geometry, in-flight parses are tombstoned
 * so a late completion can never produce a ready row whose geometry no
 * viewport owns. Covers ready + in-flight across modeling → Home → modeling
 * and removal after remount.
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { MutableRefObject } from 'react'
import type { ViewportApi } from '../Viewport'
import type { Importer } from './importController'
import type { ImportedMesh } from './normalize'
import { ReferencesList, useReferenceImport, type ReferenceImport } from './referenceImport'

afterEach(cleanup)

const MESH: ImportedMesh[] = [{ position: new Float32Array(9) } as ImportedMesh]

/** A viewport stand-in that MODELS GEOMETRY OWNERSHIP: ids present in `owned`
 *  are geometry the current viewport displays. Remount = a fresh empty map. */
function fakeViewport() {
  const owned = new Map<string, ImportedMesh[]>()
  const api = {
    addImported: (id: string, m: ImportedMesh[]) => owned.set(id, m),
    removeImported: (id: string) => owned.delete(id),
  } as unknown as ViewportApi
  return { owned, ref: { current: api } as MutableRefObject<ViewportApi | null> }
}

/** A deferred importer — the test controls WHEN each parse resolves. */
function deferredImporter() {
  const pending: Array<(m: ImportedMesh[]) => void> = []
  const importer: Importer = {
    import: () => new Promise<ImportedMesh[]>((res) => pending.push(res)),
    dispose: () => {},
  } as Importer
  return { importer, resolveNext: () => pending.shift()?.(MESH) }
}

function Probe({ vp, importer, expose }: {
  vp: ReturnType<typeof fakeViewport>
  importer: Importer
  expose: (ri: ReferenceImport) => void
}) {
  const ri = useReferenceImport(vp.ref, () => importer)
  expose(ri)
  return (
    <>
      {ri.inputElement}
      <ReferencesList imports={ri} />
    </>
  )
}

function mount(vp = fakeViewport()) {
  const d = deferredImporter()
  let ri!: ReferenceImport
  const view = render(<Probe vp={vp} importer={d.importer} expose={(x) => { ri = x }} />)
  const pick = () => {
    const input = view.container.querySelector('input[type="file"]')!
    fireEvent.change(input, { target: { files: [new File(['solid x'], 'bracket.stl')] } })
  }
  return { vp, d, pick, get ri() { return ri } }
}

describe('the modeling-scoped reference lifecycle (Codex2 B2)', () => {
  it('a READY import clears on modeling close: row gone AND geometry dropped', async () => {
    const t = mount()
    t.pick()
    t.d.resolveNext()
    await waitFor(() => expect(screen.getByText(/triangles/)).toBeTruthy())
    expect(t.vp.owned.size).toBe(1) // the viewport owns the geometry
    t.ri.clearAll() // modeling closes
    await waitFor(() => expect(screen.queryByText('bracket.stl')).toBeNull())
    expect(t.vp.owned.size).toBe(0) // ...and the geometry went with it
  })

  it('an IN-FLIGHT import is tombstoned: a late completion never goes ready, never adds geometry', async () => {
    const t = mount()
    t.pick()
    await waitFor(() => expect(screen.getByText('parsing…')).toBeTruthy())
    t.ri.clearAll() // modeling closes while the parse is still running
    await waitFor(() => expect(screen.queryByText('bracket.stl')).toBeNull())
    t.d.resolveNext() // the parse lands AFTER close — on the tombstone
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText('bracket.stl')).toBeNull() // never resurrects
    expect(screen.queryByText(/triangles/)).toBeNull()
    expect(t.vp.owned.size).toBe(0) // the orphan was dropped, not displayed
  })

  it('modeling → Home → modeling: the remounted view starts EMPTY and a new import works; removal after remount removes', async () => {
    const t = mount()
    t.pick()
    t.d.resolveNext()
    await waitFor(() => expect(screen.getByText(/triangles/)).toBeTruthy())
    t.ri.clearAll() // → Home (viewport teardown follows)
    await waitFor(() => expect(t.ri.items).toHaveLength(0))
    expect(t.vp.owned.size).toBe(0) // the OLD viewport released everything pre-teardown
    // → modeling again: a LITERALLY FRESH viewport instance mounts (Codex3 N2)
    const remounted = fakeViewport()
    t.vp.ref.current = remounted.ref.current
    // no stale ready rows against the fresh viewport
    expect(screen.queryByText('bracket.stl')).toBeNull()
    expect(remounted.owned.size).toBe(0)
    t.pick() // a NEW import in the new modeling session
    t.d.resolveNext()
    await waitFor(() => expect(screen.getByText(/triangles/)).toBeTruthy())
    expect(remounted.owned.size).toBe(1) // the NEW viewport owns the new geometry
    t.ri.remove(t.ri.items[0].id) // removal after remount
    await waitFor(() => expect(screen.queryByText('bracket.stl')).toBeNull())
    expect(remounted.owned.size).toBe(0)
  })
})
