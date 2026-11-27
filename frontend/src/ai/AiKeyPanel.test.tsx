// ABOUTME: Tests of the API key panel: "Remember on this device" is on by default, models are offered
// ABOUTME: Owner: Gian. Server-side rendering with in-memory key stores

import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it } from 'vitest'
import { clearAiKey, setAiKey, stores, type KeyStore } from '../api/aiKey'
import { AiKeyPanel } from './AiKeyPanel'

function memoryStore(): KeyStore {
  const data = new Map<string, string>()
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  }
}

const rememberBox = (html: string) => html.match(/<label class="small ai-key-remember"><input type="checkbox"[^>]*>/)?.[0] ?? ''

describe('AiKeyPanel', () => {
  beforeEach(() => {
    stores.session = memoryStore()
    stores.local = memoryStore()
    clearAiKey()
  })

  it('remembers on this device by default for a new key', () => {
    const html = renderToStaticMarkup(<AiKeyPanel required onDone={() => undefined} />)
    expect(rememberBox(html)).toContain('checked')
    expect(html).toContain('Claude Haiku 5.5')
  })

  it('shows the real place of a key saved for the session only', () => {
    setAiKey('sk-ant-session-1234', false)
    const html = renderToStaticMarkup(<AiKeyPanel required={false} onDone={() => undefined} />)
    expect(html).toContain('for this session')
    expect(rememberBox(html)).not.toContain('checked')
  })
})
