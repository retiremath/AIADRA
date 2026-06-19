/**
 * React bindings for the settings registry (arc 20260619-1 / 6a). The registry
 * itself is framework-agnostic (`registry.ts`); these hooks subscribe React to
 * it. No registry logic lives here.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { SettingsRegistry } from './registry'
import type { SettingValue } from './descriptors'
import type { Theme } from './theme'

const RegistryContext = createContext<SettingsRegistry | null>(null)

export function SettingsProvider({
  registry,
  children,
}: {
  registry: SettingsRegistry
  children: ReactNode
}) {
  return <RegistryContext.Provider value={registry}>{children}</RegistryContext.Provider>
}

export function useRegistry(): SettingsRegistry {
  const r = useContext(RegistryContext)
  if (!r) throw new Error('useRegistry must be used within a SettingsProvider')
  return r
}

/** A single setting bound to React: `[value, setValue]`. */
export function useSetting(key: string): [SettingValue, (v: SettingValue) => void] {
  const registry = useRegistry()
  const [value, setValue] = useState<SettingValue>(() => registry.get(key))
  useEffect(() => {
    setValue(registry.get(key))
    return registry.subscribe(() => setValue(registry.get(key)))
  }, [registry, key])
  return [value, (v: SettingValue) => registry.set(key, v)]
}

/** The resolved theme, re-read whenever any setting changes. */
export function useTheme(): Theme {
  const registry = useRegistry()
  const [theme, setTheme] = useState<Theme>(() => registry.theme())
  useEffect(() => {
    setTheme(registry.theme())
    return registry.subscribe(() => setTheme(registry.theme()))
  }, [registry])
  return theme
}
