// The BROWSER half of the W-6 label check (Codex21 B1/B2) — served by Vite
// from `walk-w6-labels.mjs`. It imports the PRODUCTION furniture + overlay
// modules, lays out Display-shaped scenarios at three zoom levels, renders
// them with a WebGL renderer configured like the Viewport's, and reports:
//   B2 — every label's visible INK rectangle clears its OWN measured line
//        (dim / arc / ray / leader) by a screen-space gap;
//   B1 — the rendered text is as dark as its dimension line (the sRGB tag).
// It measures the RENDERED extent (real Chromium canvas text), which the pure
// jsdom tests cannot. It draws nothing through the engine and re-proves no
// solver: the annotation values are literals in the scenarios.
import * as THREE from 'three'
import { buildDimensionFurniture } from '/src/sketch/dimensionFurniture.ts'
import { createProfileOverlay, LABEL_FONT_PX, LABEL_PAD_PX } from '/src/sketch/profileOverlay.ts'
import { principalFrame } from '/src/sketch/planeFrame.ts'

const ann = (kind, entity, value, unit = 'mm') => ({
  id: `ann:${kind}:${entity}`,
  kind,
  value,
  unit,
  entities: [entity],
  anchors: [[0, 0, 0], [0, 0, 0]],
})
const line2 = (p1, p2, a) => ({
  points: [{ id: 'p1', world: p1 }, { id: 'p2', world: p2 }],
  segments: [{ id: 's1', start: 'p1', end: 'p2' }],
  circles: [],
  annotations: a,
  constraint_glyphs: [],
})
const SCENARIOS = {
  'free line (Codex21 B2)': line2([10, 20, 0], [50, 45, 0], [
    ann('position_x', 'p1', 10), ann('position_y', 'p1', 20), ann('angle', 's1', 32.01, 'deg'), ann('position_x', 'p2', 50),
  ]),
  'right lane, long value': line2([50, 145.25, 0], [10, 20, 0], [
    ann('position_x', 'p1', 50), ann('position_y', 'p1', 145.25), ann('angle', 's1', 252.28, 'deg'), ann('position_x', 'p2', 10),
  ]),
  'left lane, negative value': line2([-80, -60, 0], [-20, 10, 0], [
    ann('position_x', 'p1', -80), ann('position_y', 'p1', -60), ann('angle', 's1', 49.4, 'deg'), ann('position_x', 'p2', -20),
  ]),
  'vertical length + radius': {
    points: [{ id: 'a', world: [0, 0, 0] }, { id: 'b', world: [0, 30, 0] }, { id: 'c', world: [40, 10, 0] }],
    segments: [{ id: 's1', start: 'a', end: 'b' }],
    circles: [{ id: 'o1', center: 'c', radius_mm: 3 }],
    annotations: [ann('length', 's1', 30), ann('radius', 'o1', 3)],
    constraint_glyphs: [],
  },
}
const ZOOMS = [0.1, 0.2, 0.4] // worldPerPixel
const W = 900
const H = 600
const GAP_MIN_PX = 6 // the anchor puts the ink edge TEXT_LIFT_PX (9) out; allow antialias slack

const lum = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b

// distance from an axis-aligned rect to a polyline, by sampling (world units)
const rectDist = (rect, polyline) => {
  let best = Infinity
  for (let i = 0; i + 1 < polyline.length; i++) {
    const [ax, ay] = polyline[i]
    const [bx, by] = polyline[i + 1]
    for (let k = 0; k <= 200; k++) {
      const t = k / 200
      const x = ax + (bx - ax) * t
      const y = ay + (by - ay) * t
      const dx = x < rect.x0 ? rect.x0 - x : x > rect.x1 ? x - rect.x1 : 0
      const dy = y < rect.y0 ? rect.y0 - y : y > rect.y1 ? y - rect.y1 : 0
      best = Math.min(best, Math.hypot(dx, dy))
    }
  }
  return best
}

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
renderer.setSize(W, H)
document.body.appendChild(renderer.domElement)
const gl = renderer.getContext()

// darkest NEAR-GREY pixel in a screen rect (x from left, y from top; px) —
// the furniture palette is grey; the profile's blue points/lines are ignored
const darkest = (x0, y0, x1, y1) => {
  const cx0 = Math.max(0, Math.floor(x0)), cy0 = Math.max(0, Math.floor(y0))
  const cx1 = Math.min(W, Math.ceil(x1)), cy1 = Math.min(H, Math.ceil(y1))
  if (cx1 <= cx0 || cy1 <= cy0) return null
  const w = cx1 - cx0, h = cy1 - cy0
  const buf = new Uint8Array(w * h * 4)
  gl.readPixels(cx0, H - cy1, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf)
  let best = 999
  let rgb = null
  for (let i = 0; i < buf.length; i += 4) {
    const r = buf[i], g = buf[i + 1], b = buf[i + 2]
    if (Math.max(r, g, b) - Math.min(r, g, b) > 40) continue // not grey: profile geometry
    const l = lum(r, g, b)
    if (l < best) { best = l; rgb = [r, g, b] }
  }
  return best === 999 ? null : { lum: best, rgb }
}

const results = []
for (const [name, geometry] of Object.entries(SCENARIOS)) {
  for (const wpp of ZOOMS) {
    const frame = principalFrame('xy')
    const furniture = buildDimensionFurniture(geometry, frame, wpp)
    const overlay = createProfileOverlay()
    overlay.update(geometry, frame, wpp)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xe8eee2)
    scene.add(overlay.group)
    const sprites = overlay.group.children.filter((c) => c instanceof THREE.Sprite)
    furniture.labels.forEach((label, i) => {
      const sprite = sprites[i] // labels are added first, in furniture order; glyphs after
      const img = sprite.material.map.image
      const padX = LABEL_PAD_PX / img.width
      const padY = (img.height - LABEL_FONT_PX) / 2 / img.height
      const p = sprite.position, s = sprite.scale, c = sprite.center
      const full = { x0: p.x - c.x * s.x, x1: p.x + (1 - c.x) * s.x, y0: p.y - c.y * s.y, y1: p.y + (1 - c.y) * s.y }
      const ink = { x0: full.x0 + padX * s.x, x1: full.x1 - padX * s.x, y0: full.y0 + padY * s.y, y1: full.y1 - padY * s.y }
      const own = furniture.lines.filter((l) => l.owner === label.owner && (l.role === 'dim' || l.role === 'arc' || l.role === 'ray' || l.role === 'leader'))
      const minDist = Math.min(...own.map((l) => rectDist(ink, l.points.map((q) => [q[0], q[1]]))))
      const minDistPx = minDist / wpp
      // B1: render with the camera centred on THIS label; sample its ink rect and its own line
      const cx = (ink.x0 + ink.x1) / 2, cy = (ink.y0 + ink.y1) / 2
      // the frustum is in CAMERA space; the camera sits over the label
      const cam = new THREE.OrthographicCamera(-(W / 2) * wpp, (W / 2) * wpp, (H / 2) * wpp, -(H / 2) * wpp, 0.01, 1000)
      cam.position.set(cx, cy, 100)
      cam.lookAt(cx, cy, 0)
      renderer.render(scene, cam)
      const toPx = (x, y) => [(x - (cx + cam.left)) / wpp, ((cy + cam.top) - y) / wpp]
      const [ix0, iy1] = toPx(ink.x0, ink.y0)
      const [ix1, iy0] = toPx(ink.x1, ink.y1)
      const text = darkest(ix0, iy0, ix1, iy1)
      // sample the OWN line at its point nearest the label (always on screen)
      let nearest = null, nd = Infinity
      for (const l of own) {
        for (let i = 0; i + 1 < l.points.length; i++) {
          const [ax, ay] = l.points[i], [bx, by] = l.points[i + 1]
          for (let k = 0; k <= 50; k++) {
            const tt = k / 50, x = ax + (bx - ax) * tt, y = ay + (by - ay) * tt
            const d = Math.hypot(x - cx, y - cy)
            if (d < nd) { nd = d; nearest = [x, y] }
          }
        }
      }
      const [mx, my] = toPx(nearest[0], nearest[1])
      const lineSample = darkest(mx - 3, my - 3, mx + 3, my + 3)
      results.push({
        scenario: name, wpp, text: label.text, owner: label.owner, outward: label.outward,
        minDistPx: Math.round(minDistPx * 100) / 100,
        ok2: minDistPx >= GAP_MIN_PX,
        textLum: text ? Math.round(text.lum) : null, textRgb: text?.rgb ?? null,
        lineLum: lineSample ? Math.round(lineSample.lum) : null,
        // B1: the darkest grey in the ink must be the palette grey 0x4b5563
        // (sRGB luminance 84); pale (untagged) textures read 150+. The line
        // sample is reported for the eye only: a 1 px antialiased line never
        // yields a fully covered pixel, so its darkest pixel is coverage-bound.
        ok1: !!text && text.lum <= 100,
      })
    })
    overlay.dispose()
  }
}
// one last frame for the screenshot: the Codex21 scenario at 0.2, whole
{
  const geometry = SCENARIOS['free line (Codex21 B2)']
  const frame = principalFrame('xy')
  const overlay = createProfileOverlay()
  overlay.update(geometry, frame, 0.2)
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0xe8eee2)
  scene.add(overlay.group)
  const cam = new THREE.OrthographicCamera(-90, 90, 60, -60, 0.01, 1000)
  cam.position.set(30, 32, 100)
  cam.lookAt(30, 32, 0)
  renderer.render(scene, cam)
}
window.__w6 = { results, done: true }
