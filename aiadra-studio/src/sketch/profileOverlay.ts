/**
 * The profile-sketch overlay (ADR/0044 A4; arc 20260730-1) — solved geometry,
 * grey derived dimensions, and constraint glyphs, rendered in WORLD space.
 *
 * It renders `ProfileGraphPreview` (live, while drawing) and `V2ProfileSketch`
 * (committed, from Display v1.4) through the SAME path, because they carry the
 * same geometry members. Preview and committed display therefore cannot drift
 * apart at the renderer either.
 *
 * Everything drawn here is DERIVED and comes from the engine: world points,
 * dimension values, anchor positions. This module measures nothing. If a
 * dimension reads 20.000 it is because the engine solved 20.000 — not because
 * Studio rounded 19.9997.
 *
 * Grey is the Creo convention for a WEAK (auto) dimension: the sketch is
 * determinate, but the user has not asserted these values. When BS-3 brings
 * dimensions-as-facts, an asserted dimension gets the strong colour and this
 * palette is where that distinction will live.
 */
import * as THREE from 'three'
import type { ConstraintGlyph, ProfileAnnotation } from '../display/contract'
import { frameToWorld, SKETCH_LIFT_MM, type PlaneFrameTS } from './planeFrame'
import { buildDimensionFurniture } from './dimensionFurniture'
import { formatAnnotation } from './annotationFormat'

// Back-compat re-export: the formatter moved to `annotationFormat` (W-4) so
// the furniture builder shares it without a module cycle.
export { formatAnnotation }

/** The geometry members shared by a live preview and a committed profile. */
export interface ProfileGeometry {
  points: { id: string; world: [number, number, number] }[]
  segments: { id: string; start: string; end: string }[]
  circles: { id: string; center: string; radius_mm: number }[]
  annotations: ProfileAnnotation[]
  constraint_glyphs: ConstraintGlyph[]
}

export interface ProfileOverlay {
  group: THREE.Group
  /** Re-render from an engine result. `null` clears without disposing.
   *  `worldPerPixel` drives the furniture's screen-constant sizing (W-4). */
  update(geometry: ProfileGeometry | null, frame: PlaneFrameTS | null, worldPerPixel: number): void
  /** Camera zoom / canvas resize: re-render the LAST inputs at the new
   *  scale (no-op below a 2% delta or with nothing rendered). */
  setViewScale(worldPerPixel: number): void
  dispose(): void
}

// Creo-family palette: solved profile geometry reads as real geometry; weak
// dimensions and constraint markers recede.
const COLOR_PROFILE = 0x1d4ed8
const COLOR_POINT = 0x0f2d6b
// W-6 (Petre's walk 2026-09-06): the auto (weak) dimension grey must READ
// on the sketch plane's fill — dark slate, still visibly not the profile
// blue that strong intent will take (Creo: weak = grey, strong = the
// dimension colour).
const COLOR_WEAK_DIM = 0x4b5563
const COLOR_GLYPH = 0x2f7d32

const CIRCLE_SEGMENTS = 96

// W-6: the label texture is sized to ITS text (no fixed 2:1 canvas whose
// glyphs filled a third of the height), and the caller scales the sprite so
// the font's em height on screen equals the furniture's pixel size.
export const LABEL_FONT_PX = 64
export const LABEL_PAD_PX = 10
const LABEL_FONT = `600 ${LABEL_FONT_PX}px system-ui, sans-serif`

export interface LabelSprite {
  sprite: THREE.Sprite
  /** texture size in texture px */
  w: number
  h: number
  /** the font size in texture px — `h / em` is the sprite-height factor */
  em: number
}

function labelSprite(text: string, color: number): LabelSprite {
  const cv = document.createElement('canvas')
  const measure = cv.getContext('2d')
  let textW = text.length * LABEL_FONT_PX * 0.6 // jsdom: no 2d context
  if (measure) {
    measure.font = LABEL_FONT
    textW = measure.measureText(text).width
  }
  const w = Math.max(8, Math.ceil(textW + LABEL_PAD_PX * 2))
  const h = Math.ceil(LABEL_FONT_PX * 1.3)
  cv.width = w // resizing resets the context state — set the font again
  cv.height = h
  const ctx = cv.getContext('2d')
  if (ctx) {
    ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`
    ctx.font = LABEL_FONT
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, w / 2, h / 2)
  }
  const tex = new THREE.CanvasTexture(cv)
  // Codex21 B1: the canvas holds COLOUR pixels (the CSS grey) — without the
  // sRGB tag the renderer treats them as linear and the text renders pale.
  tex.colorSpace = THREE.SRGBColorSpace
  tex.needsUpdate = true
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true })
  const sprite = new THREE.Sprite(mat)
  sprite.renderOrder = 10
  return { sprite, w, h, em: LABEL_FONT_PX }
}

/** The sprite's anchor (`Sprite.center`, 0..1 in the texture) that puts the
 *  label's near INK edge on the furniture's anchor point, on the OUTWARD
 *  side (Codex21 B2): a horizontal outward anchors the left/right ink edge,
 *  a vertical one the bottom/top em edge, a diagonal one the near corner; a
 *  negligible component stays centred; no outward = centred (glyphs). Pure. */
export function labelAnchor(
  outward: [number, number] | undefined,
  l: Pick<LabelSprite, 'w' | 'h' | 'em'>,
): { x: number; y: number } {
  if (!outward) return { x: 0.5, y: 0.5 }
  const padX = LABEL_PAD_PX / l.w // the ink starts after the horizontal pad
  const padY = (l.h - l.em) / 2 / l.h // the em box inside the texture height
  const EPS = 0.05
  const x = outward[0] > EPS ? padX : outward[0] < -EPS ? 1 - padX : 0.5
  const y = outward[1] > EPS ? padY : outward[1] < -EPS ? 1 - padY : 0.5
  return { x, y }
}

/** The sprite scale (world units) that puts the label's EM height at
 *  `heightMm` (= the furniture's pixel size × worldPerPixel). Pure. */
export function labelScale(l: Pick<LabelSprite, 'w' | 'h' | 'em'>, heightMm: number): { x: number; y: number } {
  const y = heightMm * (l.h / l.em)
  return { x: y * (l.w / l.h), y }
}

/** The two-character marker Creo shows for a constraint. */
export function glyphLabel(kind: ConstraintGlyph['kind']): string {
  return kind === 'horizontal' ? 'H' : 'V'
}

const v3 = (p: [number, number, number]) => new THREE.Vector3(p[0], p[1], p[2])

export function createProfileOverlay(): ProfileOverlay {
  const group = new THREE.Group()
  group.name = 'profile-overlay'
  const disposables: { dispose(): void }[] = []

  const clear = () => {
    for (const child of [...group.children]) group.remove(child)
    for (const d of disposables.splice(0)) d.dispose()
  }

  const addLine = (pts: THREE.Vector3[], color: number, width = 1) => {
    const geom = new THREE.BufferGeometry().setFromPoints(pts)
    const mat = new THREE.LineBasicMaterial({ color, linewidth: width })
    group.add(new THREE.Line(geom, mat))
    disposables.push(geom, mat)
  }

  const addLabel = (text: string, at: THREE.Vector3, color: number, heightMm: number, outward?: [number, number]) => {
    const l = labelSprite(text, color)
    const sprite = l.sprite
    sprite.position.copy(at)
    const sc = labelScale(l, heightMm)
    sprite.scale.set(sc.x, sc.y, 1)
    const anchor = labelAnchor(outward, l)
    sprite.center.set(anchor.x, anchor.y)
    group.add(sprite)
    disposables.push(sprite.material, (sprite.material as THREE.SpriteMaterial).map as THREE.Texture)
  }

  // The LAST inputs, so a zoom/resize can re-render at the new scale
  // without a fresh engine result (W-4 setViewScale).
  let lastGeometry: ProfileGeometry | null = null
  let lastFrame: PlaneFrameTS | null = null
  let lastWpp = 0

  const render = () => {
    clear()
    const geometry = lastGeometry
    const frame = lastFrame
    if (geometry === null || frame === null) return
    const byId = new Map(geometry.points.map((p) => [p.id, v3(p.world)]))

    for (const s of geometry.segments) {
      const a = byId.get(s.start)
      const b = byId.get(s.end)
      if (a && b) addLine([a, b], COLOR_PROFILE, 2)
    }

    const n = new THREE.Vector3(...frame.normal).normalize()
    for (const c of geometry.circles) {
      const centre = byId.get(c.center)
      if (!centre) continue
      // Build the circle in the SKETCH plane: any vector orthogonal to the
      // frame normal spans it, so the circle can never tilt out of plane.
      const u = new THREE.Vector3(1, 0, 0)
      if (Math.abs(u.dot(n)) > 0.9) u.set(0, 1, 0)
      u.crossVectors(n, u).normalize()
      const v = new THREE.Vector3().crossVectors(n, u).normalize()
      const pts: THREE.Vector3[] = []
      for (let i = 0; i <= CIRCLE_SEGMENTS; i++) {
        const t = (i / CIRCLE_SEGMENTS) * Math.PI * 2
        pts.push(
          centre
            .clone()
            .addScaledVector(u, Math.cos(t) * c.radius_mm)
            .addScaledVector(v, Math.sin(t) * c.radius_mm),
        )
      }
      addLine(pts, COLOR_PROFILE, 2)
    }

    for (const p of byId.values()) {
      const geom = new THREE.BufferGeometry().setFromPoints([p])
      const mat = new THREE.PointsMaterial({ color: COLOR_POINT, size: 5, sizeAttenuation: false })
      group.add(new THREE.Points(geom, mat))
      disposables.push(geom, mat)
    }

    // W-4: dimension FURNITURE — the batch module owns bbox/side/lane
    // policy and pixel→world sizing; this overlay only installs what it
    // returns. The raw anchor-segment drawing (the walk's "vector to the
    // origin") is gone.
    const furniture = buildDimensionFurniture(geometry, frame, lastWpp)
    for (const ln of furniture.lines) {
      addLine(ln.points.map((p) => v3(p)), COLOR_WEAK_DIM)
    }
    for (const l of furniture.labels) {
      addLabel(l.text, v3(l.at), COLOR_WEAK_DIM, l.heightMm, l.outward)
    }
    for (const g of furniture.glyphs) {
      addLabel(g.text, v3(g.at), COLOR_GLYPH, g.heightMm)
    }
  }

  const update = (
    geometry: ProfileGeometry | null,
    frame: PlaneFrameTS | null,
    worldPerPixel: number,
  ) => {
    lastGeometry = geometry
    lastFrame = frame
    if (worldPerPixel > 0) lastWpp = worldPerPixel
    render()
  }

  const setViewScale = (worldPerPixel: number) => {
    if (!(worldPerPixel > 0) || lastGeometry === null) return
    if (lastWpp > 0 && Math.abs(worldPerPixel - lastWpp) / lastWpp < 0.02) return
    lastWpp = worldPerPixel
    render()
  }

  return {
    group,
    update,
    setViewScale,
    dispose() {
      clear()
    },
  }
}

/** The in-progress line chain, plane-local mm (DRAWN nominals — never
 *  solved output). */
export interface ChainEchoState {
  pending: { u: number; v: number }[]
  cursor: { u: number; v: number } | null
}

export interface ChainEcho {
  group: THREE.Group
  update(chain: ChainEchoState | null, frame: PlaneFrameTS | null): void
  dispose(): void
}

// The v1 pad's rubber grey (sketchEditOverlay) — one idiom across both lanes.
const COLOR_RUBBER = 0x64748b

/**
 * The chain ECHO (W-2) — the only overlay drawn from Studio-side coordinates.
 *
 * The engine previews the chain PER COMPLETED SEGMENT (Codex11 B1), so this
 * echo is NOT the run's only visibility — it carries what the solve cannot:
 * the rubber segment to the live cursor (never part of the graph) and the
 * instant DRAWN-nominal feedback in the beat between a click and its
 * asynchronous solve reply. Confirmed chain in the profile colour, rubber in
 * the v1 pad's grey. Display-only by construction — the solved result always
 * arrives through the ordinary preview path and overdraws the nominals.
 */
export function createChainEcho(): ChainEcho {
  const group = new THREE.Group()
  group.name = 'profile-chain-echo'
  const disposables: { dispose(): void }[] = []

  const clear = () => {
    for (const child of [...group.children]) group.remove(child)
    for (const d of disposables.splice(0)) d.dispose()
  }

  const addLine = (pts: THREE.Vector3[], color: number) => {
    const geom = new THREE.BufferGeometry().setFromPoints(pts)
    const mat = new THREE.LineBasicMaterial({ color })
    group.add(new THREE.Line(geom, mat))
    disposables.push(geom, mat)
  }

  const update = (chain: ChainEchoState | null, frame: PlaneFrameTS | null) => {
    clear()
    if (chain === null || frame === null || chain.pending.length === 0) return
    const world = (p: { u: number; v: number }) =>
      new THREE.Vector3(...frameToWorld(frame, p.u, p.v, SKETCH_LIFT_MM))
    const pts = chain.pending.map(world)
    if (pts.length >= 2) addLine(pts, COLOR_PROFILE)
    const geom = new THREE.BufferGeometry().setFromPoints(pts)
    const mat = new THREE.PointsMaterial({ color: COLOR_POINT, size: 5, sizeAttenuation: false })
    group.add(new THREE.Points(geom, mat))
    disposables.push(geom, mat)
    if (chain.cursor !== null) {
      addLine([pts[pts.length - 1], world(chain.cursor)], COLOR_RUBBER)
    }
  }

  return {
    group,
    update,
    dispose() {
      clear()
    },
  }
}
