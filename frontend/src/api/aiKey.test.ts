// ABOUTME: Tests of the visitor's API key storage (decision D43): where it is kept and when it is sent
// ABOUTME: In-memory stores stand in for the browser's; a failing store must not break the app

import { beforeEach, describe, expect, it } from 'vitest'
import {
  AI_KEY_HEADER,
  aiKeyHeaders,
  clearAiKey,
  getAiKey,
  isAiKeyRemembered,
  maskKey,
  setAiKey,
  stores,
  type KeyStore,
} from './aiKey'

function memoryStore(): KeyStore & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  }
}

const brokenStore: KeyStore = {
  getItem: () => {
    throw new Error('blocked')
  },
  setItem: () => {
    throw new Error('blocked')
  },
  removeItem: () => {
    throw new Error('blocked')
  },
}

describe('AI key storage', () => {
  let session: ReturnType<typeof memoryStore>
  let local: ReturnType<typeof memoryStore>

  beforeEach(() => {
    session = memoryStore()
    local = memoryStore()
    stores.session = session
    stores.local = local
    clearAiKey()
  })

  it('sends no header without a key', () => expect(aiKeyHeaders()).toEqual({}))

  it('keeps the key for the session only by default', () => {
    setAiKey('  sk-ant-session  ', false)
    expect(getAiKey()).toBe('sk-ant-session')
    expect(session.data.size).toBe(1)
    expect(local.data.size).toBe(0)
    expect(isAiKeyRemembered()).toBe(false)
    expect(aiKeyHeaders()).toEqual({ [AI_KEY_HEADER]: 'sk-ant-session' })
  })

  it('remembers the key on the device only when asked, and moves it between stores', () => {
    setAiKey('sk-ant-local', true)
    expect(local.data.size).toBe(1)
    expect(session.data.size).toBe(0)
    expect(isAiKeyRemembered()).toBe(true)
    setAiKey('sk-ant-local', false)
    expect(local.data.size).toBe(0)
    expect(session.data.size).toBe(1)
  })

  it('forgets the key everywhere', () => {
    setAiKey('sk-ant-x', true)
    clearAiKey()
    expect(getAiKey()).toBeNull()
    expect(local.data.size + session.data.size).toBe(0)
  })

  it('treats a blank key as no key', () => {
    setAiKey('sk-ant-x', false)
    setAiKey('   ', false)
    expect(getAiKey()).toBeNull()
  })

  it('keeps working in memory when storage is blocked', () => {
    stores.session = brokenStore
    stores.local = brokenStore
    setAiKey('sk-ant-memory', false)
    expect(getAiKey()).toBe('sk-ant-memory')
    clearAiKey()
    expect(getAiKey()).toBeNull()
  })

  it('masks all but the last four characters', () => {
    expect(maskKey('sk-ant-api03-abcd1234')).toBe('…1234')
    expect(maskKey('abc')).toBe('…')
  })
})
