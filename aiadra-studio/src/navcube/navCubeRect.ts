/**
 * Nav-cube corner-rect math (arc 20260625-1 / 6c; Codex1 B1). PURE + headless-
 * testable — the part of the scissor-corner overlay that is easy to get wrong
 * (device-pixel vs CSS-pixel, GL's bottom-left origin, pointer→NDC within the
 * sub-rect). The three.js scene/render in `navCube.ts` consumes these.
 */

export type Corner = 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left'

export interface NavCubeLayout {
  /** Cube square edge length, CSS px. */
  sizeCss: number
  /** Margin from the canvas edge, CSS px. */
  marginCss: number
  corner: Corner
}

export const DEFAULT_NAV_CUBE_LAYOUT: NavCubeLayout = {
  sizeCss: 96,
  marginCss: 12,
  corner: 'top-right',
}

/** The cube's top-left corner in CSS pixels (top-left canvas origin). */
function topLeftCss(layout: NavCubeLayout, canvasWcss: number, canvasHcss: number): [number, number] {
  const { sizeCss: s, marginCss: m, corner } = layout
  const left = corner === 'top-right' || corner === 'bottom-right' ? canvasWcss - m - s : m
  const top = corner === 'top-left' || corner === 'top-right' ? m : canvasHcss - m - s
  return [left, top]
}

/**
 * The scissor/viewport rect for `renderer.setViewport`/`setScissor`, in **CSS
 * pixels** with GL's bottom-left origin. NB: three.js multiplies these by the
 * renderer's `pixelRatio` internally — passing device pixels here double-counts
 * the DPR and pushes the cube off-screen on a scaled display (the round-3 fix).
 */
export function navCubeViewportRect(
  layout: NavCubeLayout,
  canvasWcss: number,
  canvasHcss: number,
): { x: number; y: number; width: number; height: number } {
  const [leftCss, topCss] = topLeftCss(layout, canvasWcss, canvasHcss)
  const bottomFromTopCss = topCss + layout.sizeCss
  return {
    x: leftCss,
    y: canvasHcss - bottomFromTopCss, // flip to bottom-left origin (still CSS px)
    width: layout.sizeCss,
    height: layout.sizeCss,
  }
}

/** Is a pointer (CSS px, top-left origin, canvas-relative) inside the cube rect? */
export function pointerInNavCube(
  layout: NavCubeLayout,
  canvasWcss: number,
  canvasHcss: number,
  px: number,
  py: number,
): boolean {
  const [left, top] = topLeftCss(layout, canvasWcss, canvasHcss)
  return px >= left && px <= left + layout.sizeCss && py >= top && py <= top + layout.sizeCss
}

/**
 * Map a pointer (CSS px, top-left, canvas-relative) to NDC within the cube rect
 * (x,y ∈ [−1,1], y up). Caller should gate on `pointerInNavCube` first; values
 * outside [−1,1] mean the pointer is outside the cube.
 */
export function pointerToNavCubeNdc(
  layout: NavCubeLayout,
  canvasWcss: number,
  canvasHcss: number,
  px: number,
  py: number,
): [number, number] {
  const [left, top] = topLeftCss(layout, canvasWcss, canvasHcss)
  const u = (px - left) / layout.sizeCss
  const v = (py - top) / layout.sizeCss
  return [u * 2 - 1, -(v * 2 - 1)]
}
