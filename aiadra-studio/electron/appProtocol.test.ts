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

  it('keeps every .. traversal attempt confined (no escape from the root)', () => {
    // URL normalization collapses literal AND percent-encoded `..` within the
    // origin; the helper's explicit `..` segment check + main.ts's realpath guard
    // are defense-in-depth. The invariant under test: the result is either
    // rejected, or a confined relative path that contains no `..` and is not absolute.
    const attempts = [
      'app://bundle/../secret',
      'app://bundle/assets/../../secret',
      'app://bundle/%2e%2e/secret',
      'app://bundle/assets/%2e%2e/%2e%2e/secret',
      'app://bundle/a/b/../../../secret',
    ]
    for (const url of attempts) {
      const r = resolveAppAssetRelPath(url)
      if (r.ok) {
        expect(r.relPath).not.toContain('..')
        expect(r.relPath.startsWith('/')).toBe(false)
      } else {
        expect([400, 403, 404]).toContain(r.status)
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
