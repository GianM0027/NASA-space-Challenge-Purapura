// ABOUTME: The visitor's own Anthropic API key (decision D43): kept in this browser, sent only with AI calls
// ABOUTME: Owner: Gian. Session storage by default; local storage only when the visitor asks to remember it

/** Header the backend reads the key from (GET /api/ai/config reports the same name). */
export const AI_KEY_HEADER = 'X-Anthropic-Api-Key'
const STORAGE_KEY = 'lunarnav.anthropicApiKey'
const CHANGE_EVENT = 'lunarnav-ai-key'

/** Minimal Storage surface, so tests can pass in-memory stores. */
export interface KeyStore {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

// Storage access can throw (private windows, blocked site data): every helper tolerates it.
function browserStore(kind: 'session' | 'local'): KeyStore | null {
  try {
    return kind === 'session' ? globalThis.sessionStorage ?? null : globalThis.localStorage ?? null
  } catch {
    return null
  }
}

function read(store: KeyStore | null): string | null {
  try {
    return store?.getItem(STORAGE_KEY) || null
  } catch {
    return null
  }
}

function write(store: KeyStore | null, value: string | null): void {
  try {
    if (value === null) store?.removeItem(STORAGE_KEY)
    else store?.setItem(STORAGE_KEY, value)
  } catch {
    // Not saved: the key then lasts only as long as this page's memory copy below.
  }
}

// Fallback when no storage works at all: the key lives until the page is reloaded.
let memoryKey: string | null = null

/** The stores used by the helpers; replaceable in tests. */
export const stores: { session: KeyStore | null; local: KeyStore | null } = {
  session: browserStore('session'),
  local: browserStore('local'),
}

/** The saved key, or null. A key typed this session wins over a remembered one. */
export function getAiKey(): string | null {
  return read(stores.session) ?? read(stores.local) ?? memoryKey
}

/** Whether the saved key is remembered across browser restarts on this device. */
export function isAiKeyRemembered(): boolean {
  return read(stores.local) !== null
}

/** Save `key` (trimmed) for this tab session, or on this device when `remember` is true. */
export function setAiKey(key: string, remember: boolean): void {
  const value = key.trim()
  if (!value) return clearAiKey()
  write(stores.session, remember ? null : value)
  write(stores.local, remember ? value : null)
  memoryKey = value
  notify()
}

/** Forget the key everywhere in this browser. */
export function clearAiKey(): void {
  write(stores.session, null)
  write(stores.local, null)
  memoryKey = null
  notify()
}

/** Headers carrying the key, for the AI requests only; empty without a key. */
export function aiKeyHeaders(): Record<string, string> {
  const key = getAiKey()
  return key ? { [AI_KEY_HEADER]: key } : {}
}

/** Show only the last characters of a key, e.g. for "Key ending in …a1b2". */
export function maskKey(key: string): string {
  return key.length <= 4 ? '…' : `…${key.slice(-4)}`
}

function notify(): void {
  try {
    globalThis.dispatchEvent?.(new Event(CHANGE_EVENT))
  } catch {
    // No event target (tests in Node): nothing listens anyway.
  }
}

/** Call `listener` whenever the key changes; returns the unsubscribe function. */
export function onAiKeyChange(listener: () => void): () => void {
  globalThis.addEventListener?.(CHANGE_EVENT, listener)
  return () => globalThis.removeEventListener?.(CHANGE_EVENT, listener)
}
