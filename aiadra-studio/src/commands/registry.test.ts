import { describe, expect, it, vi } from 'vitest'
import {
  COMMANDS,
  COMMANDS_BY_ID,
  commandsInGroup,
  dispatchShortcut,
  normalizeChord,
} from './registry'
import type { CommandActions, CommandContext } from './types'

function ctx(over: Partial<CommandContext> = {}): CommandContext {
  const merged: CommandContext = {
    hasCanonicalPart: false,
    hasReferenceGeometry: false,
    hasRenderableScene: false,
    mode: 'shading-edges',
    gridVisible: true,
    ...over,
  }
  merged.hasRenderableScene = merged.hasCanonicalPart || merged.hasReferenceGeometry
  return merged
}

const mkActions = (): CommandActions => ({
  fit: vi.fn(),
  reset: vi.fn(),
  setMode: vi.fn(),
  toggleGrid: vi.fn(),
})

describe('command taxonomy', () => {
  it('has stable, unique ids', () => {
    const ids = COMMANDS.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  // --- Codex1 B1: the imported-only reference lane keeps its affordances ---
  it('B1: an imported-only scene keeps fit/reset, display modes, and grid', () => {
    const imported = ctx({ hasReferenceGeometry: true })
    expect(COMMANDS_BY_ID['view.fit'].isEnabled(imported)).toBe(true)
    expect(COMMANDS_BY_ID['view.reset'].isEnabled(imported)).toBe(true)
    expect(COMMANDS_BY_ID['display.wireframe'].isEnabled(imported)).toBe(true)
    expect(COMMANDS_BY_ID['display.hidden-line'].isEnabled(imported)).toBe(true)
    expect(COMMANDS_BY_ID['scene.grid'].isEnabled(imported)).toBe(true)
  })

  it('B1: an empty scene disables geometry commands but keeps grid', () => {
    const empty = ctx()
    expect(COMMANDS_BY_ID['view.fit'].isEnabled(empty)).toBe(false)
    expect(COMMANDS_BY_ID['display.wireframe'].isEnabled(empty)).toBe(false)
    expect(COMMANDS_BY_ID['scene.grid'].isEnabled(empty)).toBe(true) // ground plane is always useful
  })

  it('B1: a canonical-Part scene enables view + display commands', () => {
    const canonical = ctx({ hasCanonicalPart: true })
    expect(COMMANDS_BY_ID['view.fit'].isEnabled(canonical)).toBe(true)
    expect(COMMANDS_BY_ID['display.shading'].isEnabled(canonical)).toBe(true)
  })

  it('B1: no 6b command is canonical-only — reference-only enables exactly what canonical does', () => {
    const imported = ctx({ hasReferenceGeometry: true })
    const canonical = ctx({ hasCanonicalPart: true })
    for (const c of COMMANDS) {
      expect(c.isEnabled(imported)).toBe(c.isEnabled(canonical))
    }
  })

  it('active state reflects the live mode + grid', () => {
    expect(COMMANDS_BY_ID['display.shading-edges'].isActive!(ctx({ mode: 'shading-edges' }))).toBe(true)
    expect(COMMANDS_BY_ID['display.wireframe'].isActive!(ctx({ mode: 'shading-edges' }))).toBe(false)
    expect(COMMANDS_BY_ID['scene.grid'].isActive!(ctx({ gridVisible: true }))).toBe(true)
    expect(COMMANDS_BY_ID['scene.grid'].isActive!(ctx({ gridVisible: false }))).toBe(false)
  })

  it('run dispatches to the injected actions (N3 — no captured state)', () => {
    const a = mkActions()
    const c = ctx({ hasCanonicalPart: true })
    COMMANDS_BY_ID['view.fit'].run(a, c)
    expect(a.fit).toHaveBeenCalledTimes(1)
    COMMANDS_BY_ID['view.reset'].run(a, c)
    expect(a.reset).toHaveBeenCalledTimes(1)
    COMMANDS_BY_ID['display.wireframe'].run(a, c)
    expect(a.setMode).toHaveBeenCalledWith('wireframe')
    COMMANDS_BY_ID['scene.grid'].run(a, c)
    expect(a.toggleGrid).toHaveBeenCalledTimes(1)
  })

  it('the operations group is a reserved disabled placeholder (D10 boundary / N6)', () => {
    const op = commandsInGroup('operations')
    expect(op).toHaveLength(1)
    expect(op[0].isEnabled(ctx({ hasCanonicalPart: true }))).toBe(false)
  })
})

describe('keyboard shortcuts', () => {
  it('normalizes chords (mod for ctrl/cmd; lowercased)', () => {
    expect(normalizeChord({ key: 'F', ctrlKey: false, metaKey: false, shiftKey: false, altKey: false })).toBe('f')
    expect(normalizeChord({ key: 'f', ctrlKey: true, metaKey: false, shiftKey: false, altKey: false })).toBe('mod+f')
    expect(normalizeChord({ key: 'g', ctrlKey: false, metaKey: false, shiftKey: true, altKey: false })).toBe('shift+g')
  })

  it('dispatches enabled commands and reports a hit', () => {
    const a = mkActions()
    expect(dispatchShortcut('f', ctx({ hasReferenceGeometry: true }), a)).toBe(true)
    expect(a.fit).toHaveBeenCalled()

    const a2 = mkActions()
    expect(dispatchShortcut('1', ctx({ hasCanonicalPart: true }), a2)).toBe(true) // mode hotkey
    expect(a2.setMode).toHaveBeenCalled()

    const a3 = mkActions()
    expect(dispatchShortcut('g', ctx(), a3)).toBe(true) // grid works even with no scene
    expect(a3.toggleGrid).toHaveBeenCalled()
  })

  it('does not fire a disabled command, and ignores unknown chords', () => {
    const a = mkActions()
    expect(dispatchShortcut('f', ctx(), a)).toBe(false) // fit needs a scene
    expect(a.fit).not.toHaveBeenCalled()
    expect(dispatchShortcut('z', ctx({ hasCanonicalPart: true }), mkActions())).toBe(false)
  })
})
