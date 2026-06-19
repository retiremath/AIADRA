/**
 * Display-mode taxonomy + semantics matrix (ADR/0033 D7; arc 20260610-1).
 * The Creo set on the true-edge foundation — this module is the single source
 * of truth for what each mode renders, as plain data (table-driven, testable
 * without three.js).
 *
 * Two-phase posture (ADR/0033 D6): while the camera moves, modes work per-pixel
 * on the GPU using the base true model edges + the depth buffer ("live" flags
 * below). On camera-settle the exact classified HLR overlay swaps in and the
 * base edge passes hide (`overlaySegmentStyle` below). Never per-frame HLR.
 *
 * Codex1 B2 (this arc): Hidden Line's live dim pass renders ALL edges with
 * depth-testing OFF (see-through), underneath the depth-tested bright pass —
 * without that, hidden edges are suppressed by the face depth buffer and the
 * mode silently collapses into No Hidden (the stopgap's exact mis-naming).
 */

export type DisplayMode = 'wireframe' | 'hidden-line' | 'no-hidden' | 'shading' | 'shading-edges'

export const DISPLAY_MODES: DisplayMode[] = [
  'wireframe',
  'hidden-line',
  'no-hidden',
  'shading',
  'shading-edges',
]

export const MODE_LABELS: Record<DisplayMode, string> = {
  wireframe: 'Wireframe',
  'hidden-line': 'Hidden Line',
  'no-hidden': 'No Hidden',
  shading: 'Shading',
  'shading-edges': 'Shading With Edges',
}

/**
 * Face rendering per mode. `paper` is the Creo unshaded-body look: the part is
 * an OPAQUE background-colored body that occludes the grid and everything
 * behind it (a `colorWrite:false` depth-only body cannot do this — whatever was
 * drawn before it stays visible through the part).
 */
export type FaceStyle = 'shaded' | 'paper' | 'none'

/** Live-phase render flags for the canonical part (and reference imports). */
export interface ModeFlags {
  faceStyle: FaceStyle
  /** Faces occlude (write the depth buffer). Off only in wireframe. */
  facesDepthWrite: boolean
  /** The depth-tested visible-edge pass. */
  brightEdgesVisible: boolean
  /** Wireframe disables depth-testing so every edge shows see-through. */
  brightEdgesDepthTest: boolean
  /** B2: the see-through all-edges dim pass — Hidden Line only. */
  dimEdgesVisible: boolean
  /** B2: MUST be false whenever the dim pass is visible. */
  dimEdgesDepthTest: boolean
}

const MODE_FLAGS: Record<DisplayMode, ModeFlags> = {
  shading: {
    faceStyle: 'shaded',
    facesDepthWrite: true,
    brightEdgesVisible: false,
    brightEdgesDepthTest: true,
    dimEdgesVisible: false,
    dimEdgesDepthTest: true,
  },
  'shading-edges': {
    faceStyle: 'shaded',
    facesDepthWrite: true,
    brightEdgesVisible: true,
    brightEdgesDepthTest: true,
    dimEdgesVisible: false,
    dimEdgesDepthTest: true,
  },
  'no-hidden': {
    faceStyle: 'paper',
    facesDepthWrite: true,
    brightEdgesVisible: true,
    brightEdgesDepthTest: true,
    dimEdgesVisible: false,
    dimEdgesDepthTest: true,
  },
  'hidden-line': {
    faceStyle: 'paper',
    facesDepthWrite: true,
    brightEdgesVisible: true,
    brightEdgesDepthTest: true,
    dimEdgesVisible: true,
    dimEdgesDepthTest: false, // B2 — see-through, or hidden edges never show live
  },
  wireframe: {
    faceStyle: 'none',
    facesDepthWrite: false,
    brightEdgesVisible: true,
    brightEdgesDepthTest: false,
    dimEdgesVisible: false,
    dimEdgesDepthTest: true,
  },
}

export function modeFlags(mode: DisplayMode): ModeFlags {
  return MODE_FLAGS[mode]
}

/**
 * Settled-phase policy: how an exact HLR segment renders per mode, by its
 * engine classification. Applies uniformly to model-edge and outline sources
 * (per-class theming is the step-6 Appearance arc).
 *
 * Codex1 N4: Shading With Edges omits hidden segments entirely — hidden
 * outlines belong to Hidden Line, not the shaded mode.
 */
export type OverlaySegmentStyle = 'bright' | 'dim' | 'omit'

export function overlaySegmentStyle(
  mode: DisplayMode,
  visibility: 'visible' | 'hidden',
): OverlaySegmentStyle {
  switch (mode) {
    case 'shading':
      return 'omit' // no overlay at all
    case 'shading-edges':
    case 'no-hidden':
      return visibility === 'visible' ? 'bright' : 'omit'
    case 'hidden-line':
      return visibility === 'visible' ? 'bright' : 'dim'
    case 'wireframe':
      return 'bright' // every edge, no hidden distinction
  }
}

/** Whether a settled overlay replaces the base edge passes in this mode. */
export function overlayActive(mode: DisplayMode): boolean {
  return mode !== 'shading'
}
