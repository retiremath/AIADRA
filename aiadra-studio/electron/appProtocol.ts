/**
 * Pure helpers for the read-only `app://bundle` asset scheme (Codex1 B1, arc
 * 20260603-2). Kept free of `node:fs`/`node:path` so the URL→safe-relative-path
 * confinement matrix is unit-tested without launching Electron. `main.ts` joins
 * the returned relative path under the renderer root and adds the filesystem-level
 * realpath/symlink guard.
 *
 * The built renderer is served from this origin so `occt-import-js` can fetch its
 * WASM (Chromium blocks `fetch(file://)`); the handler must therefore be a tight
 * local-app boundary, never a general file server.
 */

export type ResolvedAsset = { ok: true; relPath: string } | { ok: false; status: number }

/**
 * Validate an `app://bundle/...` request URL and return a confined, forward-slash
 * relative path under the renderer root — or an HTTP-ish status to reject with.
 *
 * Rejects: non-`app:` scheme, non-`bundle` host, malformed URLs, backslashes, NUL
 * bytes, drive-letter/absolute injection, and **percent-encoded `..` traversal**
 * (scanned on the raw URL, since `new URL` would otherwise decode + normalize
 * `%2e` away). **Literal** `..` is left to URL normalization — it collapses within
 * the origin and cannot escape — and `main.ts` adds a realpath/symlink-escape
 * guard as the final backstop. Codex2 N1 (arc 20260603-2).
 */
export function resolveAppAssetRelPath(requestUrl: string): ResolvedAsset {
  // Strict raw-URL pre-scan: reject percent-encoded dots before the URL parser can
  // decode + normalize them into an innocuous-looking path.
  if (requestUrl.toLowerCase().includes('%2e')) return { ok: false, status: 403 }

  let u: URL
  try {
    u = new URL(requestUrl)
  } catch {
    return { ok: false, status: 400 }
  }
  if (u.protocol !== 'app:') return { ok: false, status: 400 }
  if (u.host !== 'bundle') return { ok: false, status: 404 }

  let pathname: string
  try {
    pathname = decodeURIComponent(u.pathname)
  } catch {
    return { ok: false, status: 400 } // malformed percent-encoding
  }
  if (pathname.includes('\0') || pathname.includes('\\')) return { ok: false, status: 400 }

  let p = pathname
  if (p === '' || p === '/') p = '/index.html'
  if (!p.startsWith('/')) return { ok: false, status: 400 }

  const segments: string[] = []
  for (const seg of p.split('/')) {
    if (seg === '' || seg === '.') continue
    if (seg === '..') return { ok: false, status: 403 } // no traversal
    segments.push(seg)
  }
  if (segments.length === 0) return { ok: false, status: 400 }
  // reject Windows drive-letter / absolute-path injection (e.g. "C:")
  if (/^[a-zA-Z]:$/.test(segments[0])) return { ok: false, status: 400 }

  return { ok: true, relPath: segments.join('/') }
}

const MIME: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.map': 'application/json',
  '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.step': 'application/step',
  '.stp': 'application/step',
  '.stl': 'model/stl',
  '.txt': 'text/plain',
}

/** Explicit content type by extension (WASM must be `application/wasm`, never text). */
export function contentTypeFor(relPath: string): string {
  const dot = relPath.lastIndexOf('.')
  const ext = dot >= 0 ? relPath.slice(dot).toLowerCase() : ''
  return MIME[ext] ?? 'application/octet-stream'
}
