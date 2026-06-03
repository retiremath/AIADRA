import { describe, expect, it } from 'vitest'
import { contentTypeFor, resolveAppAssetRelPath } from './appProtocol'

describe('resolveAppAssetRelPath — app:// confinement (Codex1 B1)', () => {
  it('maps the root to index.html', () => {
    expect(resolveAppAssetRelPath('app://bundle/')).toEqual({ ok: true, relPath: 'index.html' })
    expect(resolveAppAssetRelPath('app://bundle')).toEqual({ ok: true, relPath: 'index.html' })
  })

  it('serves a nested asset path verbatim', () => {
    expect(resolveAppAssetRelPath('app://bundle/assets/index-abc.js')).toEqual({
      ok: true,
      relPath: 'assets/index-abc.js',
    })
    expect(resolveAppAssetRelPath('app://bundle/assets/occt-import-js-x.wasm')).toEqual({
      ok: true,
      relPath: 'assets/occt-import-js-x.wasm',
    })
  })

  it('rejects a non-app scheme', () => {
    expect(resolveAppAssetRelPath('file://bundle/index.html')).toEqual({ ok: false, status: 400 })
    expect(resolveAppAssetRelPath('http://bundle/index.html')).toEqual({ ok: false, status: 400 })
  })

  it('rejects a non-bundle host', () => {
    expect(resolveAppAssetRelPath('app://evil/index.html')).toEqual({ ok: false, status: 404 })
  })

  it('strictly rejects percent-encoded .. traversal (raw pre-scan, Codex2 N1)', () => {
    expect(resolveAppAssetRelPath('app://bundle/%2e%2e/secret')).toEqual({ ok: false, status: 403 })
    expect(resolveAppAssetRelPath('app://bundle/assets/%2e%2e/%2e%2e/secret')).toEqual({ ok: false, status: 403 })
    expect(resolveAppAssetRelPath('app://bundle/%2E%2E/secret')).toEqual({ ok: false, status: 403 })
  })

  it('neutralizes literal .. via URL normalization (stays confined, never escapes)', () => {
    // Literal `..` collapses within the origin; the result is a confined path that
    // contains no `..` and is not absolute (main.ts realpath-confines it further).
    for (const url of ['app://bundle/../secret', 'app://bundle/assets/../../secret', 'app://bundle/a/b/../../../secret']) {
      const r = resolveAppAssetRelPath(url)
      expect(r.ok).toBe(true)
      if (r.ok) {
        expect(r.relPath).not.toContain('..')
        expect(r.relPath.startsWith('/')).toBe(false)
      }
    }
  })

  it('rejects backslashes and NUL bytes', () => {
    expect(resolveAppAssetRelPath('app://bundle/..\\windows')).toEqual({ ok: false, status: 400 })
    expect(resolveAppAssetRelPath('app://bundle/x%00.js')).toEqual({ ok: false, status: 400 })
  })

  it('rejects drive-letter / absolute-path injection', () => {
    expect(resolveAppAssetRelPath('app://bundle/C:/Windows/system32')).toEqual({ ok: false, status: 400 })
  })

  it('collapses . and redundant slashes safely', () => {
    expect(resolveAppAssetRelPath('app://bundle/./assets//x.js')).toEqual({ ok: true, relPath: 'assets/x.js' })
  })
})

describe('contentTypeFor', () => {
  it('returns application/wasm for .wasm (never text)', () => {
    expect(contentTypeFor('assets/occt.wasm')).toBe('application/wasm')
  })
  it('maps common asset types', () => {
    expect(contentTypeFor('index.html')).toBe('text/html')
    expect(contentTypeFor('assets/x.js')).toBe('text/javascript')
    expect(contentTypeFor('assets/x.css')).toBe('text/css')
  })
  it('falls back to octet-stream for unknown extensions', () => {
    expect(contentTypeFor('weird.xyz')).toBe('application/octet-stream')
  })
})
