// Launch electron-vite with ELECTRON_RUN_AS_NODE stripped from the environment.
//
// Some environments — notably VSCode's integrated terminal / extension host —
// export ELECTRON_RUN_AS_NODE=1. That forces the Electron binary to run as plain
// Node, so `require('electron')` returns a path string and `app` is undefined
// ("Cannot read properties of undefined (reading 'whenReady')"). Electron keys
// off the variable's PRESENCE, not its value, so blanking it (cross-env VAR=)
// does not help — it must be deleted. Doing it here keeps `npm run dev` working
// regardless of where it is launched from.
import { spawn } from 'node:child_process'

delete process.env.ELECTRON_RUN_AS_NODE

const mode = process.argv[2] === 'preview' ? 'preview' : 'dev'
const child = spawn('electron-vite', [mode], {
  stdio: 'inherit',
  shell: true, // resolve electron-vite from node_modules/.bin on win32
  env: process.env,
})
child.on('exit', (code) => process.exit(code ?? 0))
