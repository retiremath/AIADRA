// Ambient types for occt-import-js (the package ships no .d.ts) + the WASM
// asset URL import. occt-import-js is an Emscripten module: the factory accepts
// a `locateFile`/`wasmBinary` Module config and resolves to the bound API.

declare module 'occt-import-js' {
  type OcctMesh = {
    name?: string
    attributes: {
      position?: { array: number[] }
      normal?: { array: number[] }
    }
    index?: { array: number[] }
    /** Per-BREP-face index ranges. Reference render metadata only (Codex1 N2). */
    brep_faces?: { first: number; last: number; color?: number[] }[]
  }
  type OcctReadResult = { success: boolean; root?: unknown; meshes: OcctMesh[] }
  type OcctModule = {
    ReadStepFile(content: Uint8Array, params: unknown): OcctReadResult
    ReadBrepFile?(content: Uint8Array, params: unknown): OcctReadResult
    ReadIgesFile?(content: Uint8Array, params: unknown): OcctReadResult
  }
  type OcctModuleConfig = {
    locateFile?: (path: string, prefix: string) => string
    wasmBinary?: ArrayBuffer | Uint8Array
  }
  const factory: (config?: OcctModuleConfig) => Promise<OcctModule>
  export default factory
}

declare module '*?url' {
  const url: string
  export default url
}

declare module '*?inline' {
  // Vite inlines the asset as a base64 data URL string.
  const dataUrl: string
  export default dataUrl
}
