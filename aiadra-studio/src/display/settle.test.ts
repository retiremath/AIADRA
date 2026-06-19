import { describe, expect, it } from 'vitest'
import { createSettleMachine, type SettleMachine } from './settle'

/** Manual scheduler: settles fire only when the test says so. */
function harness() {
  const fired: number[] = []
  let cleared = 0
  let pending: (() => void) | null = null
  let cancelled = 0
  const machine: SettleMachine = createSettleMachine({
    settleMs: 200,
    schedule: (fn) => {
      pending = fn
      return () => {
        if (pending === fn) pending = null
        cancelled++
      }
    },
    onSettle: (seq) => fired.push(seq),
    onClear: () => cleared++,
  })
  const tick = () => {
    const fn = pending
    pending = null
    fn?.()
  }
  return {
    machine,
    tick,
    fired,
    get cleared() {
      return cleared
    },
    get cancelled() {
      return cancelled
    },
    get hasPending() {
      return pending !== null
    },
  }
}

describe('settle machine (P4 staleness discipline)', () => {
  it('issues one sequence-numbered request after the camera settles', () => {
    const h = harness()
    h.machine.cameraMoved()
    h.machine.cameraMoved()
    h.machine.cameraMoved()
    expect(h.fired).toEqual([]) // never during movement
    h.tick()
    expect(h.fired).toEqual([1])
    expect(h.machine.response(1)).toBe('accept')
  })

  it('accepts a sequence at most once (duplicate frames are stale)', () => {
    const h = harness()
    h.machine.cameraMoved()
    h.tick()
    expect(h.machine.response(1)).toBe('accept')
    expect(h.machine.response(1)).toBe('stale')
  })

  it('a response from before a camera move is stale, and the overlay is cleared', () => {
    const h = harness()
    h.machine.cameraMoved()
    h.tick() // request 1 in flight
    h.machine.cameraMoved() // user moves before the response arrives
    expect(h.cleared).toBe(1)
    expect(h.machine.response(1)).toBe('stale')
    h.tick()
    expect(h.fired).toEqual([1, 2])
    expect(h.machine.response(2)).toBe('accept')
  })

  it('movement after an accepted overlay clears it — once per movement burst', () => {
    const h = harness()
    h.machine.cameraMoved()
    h.tick()
    h.machine.response(1) // overlay attached
    h.machine.cameraMoved()
    h.machine.cameraMoved()
    h.machine.cameraMoved()
    expect(h.cleared).toBe(1) // not re-fired while already clean
  })

  it('no spurious clear when nothing was in flight or attached', () => {
    const h = harness()
    h.machine.cameraMoved()
    h.machine.cameraMoved()
    expect(h.cleared).toBe(0)
  })

  it('dispose cancels scheduling and makes everything stale', () => {
    const h = harness()
    h.machine.cameraMoved()
    h.tick()
    h.machine.dispose()
    expect(h.machine.response(1)).toBe('stale')
    h.machine.cameraMoved()
    expect(h.hasPending).toBe(false)
  })
})
