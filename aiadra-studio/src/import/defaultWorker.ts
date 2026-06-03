/**
 * The real parse-worker spawn. Isolated in its own module so the static
 * `new Worker(new URL('./importWorker.ts', ...))` (Codex1 N4 — statically
 * analyzable for Vite) is imported ONLY by the app, never by the unit tests
 * (which inject a fake worker and must not pull the occt/WASM worker graph).
 */
import type { WorkerLike } from './importController'

export function spawnImportWorker(): WorkerLike {
  return new Worker(new URL('./importWorker.ts', import.meta.url), { type: 'module' }) as unknown as WorkerLike
}
