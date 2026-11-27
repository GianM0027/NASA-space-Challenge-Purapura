// ABOUTME: Panel where a visitor adds, changes or removes their own Anthropic API key (decision D43)
// ABOUTME: Owner: Gian. The key stays in this browser; the panel says plainly where it goes

import { useState } from 'react'
import { AI_MODELS, clearAiKey, getAiKey, getAiModel, isAiKeyRemembered, maskKey, setAiKey, setAiModel, type AiModelId } from '../api/aiKey'

/**
 * Key form shown inside the AI box. `required` is true when the server has no AI of its own,
 * so the assistant does nothing until a key is added.
 */
export function AiKeyPanel(props: { required: boolean; onDone: () => void }) {
  const { required, onDone } = props
  const saved = getAiKey()
  const [draft, setDraft] = useState('')
  const [remember, setRemember] = useState(isAiKeyRemembered())
  const [model, setModel] = useState<AiModelId>(getAiModel())

  const save = () => {
    if (!draft.trim()) return
    setAiKey(draft, remember)
    setDraft('')
    onDone()
  }

  return (
    <div className="ai-key">
      <p className="small">
        {required
          ? 'The AI assistant runs on your own Anthropic API key. '
          : 'Use your own Anthropic API key for the AI. '}
        Get one at{' '}
        <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">
          console.anthropic.com
        </a>
        ; usage is billed to your Anthropic account.
      </p>
      {saved && (
        <p className="small ai-key-saved">
          Key ending in <code>{maskKey(saved)}</code>, {isAiKeyRemembered() ? 'remembered on this device' : 'for this session'}.{' '}
          <button className="link" onClick={() => clearAiKey()}>
            Remove
          </button>
        </p>
      )}
      <form
        className="ask"
        onSubmit={(event) => {
          event.preventDefault()
          save()
        }}
      >
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          aria-label="Anthropic API key"
          placeholder={saved ? 'Paste a new key to replace it' : 'sk-ant-…'}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" disabled={!draft.trim()}>
          Save
        </button>
      </form>
      <fieldset className="ai-model">
        <legend className="small">Model (token use)</legend>
        {AI_MODELS.map((option) => (
          <label key={option.id} className="small">
            <input
              type="radio"
              name="ai-model"
              value={option.id}
              checked={model === option.id}
              onChange={() => {
                setModel(option.id)
                setAiModel(option.id)
              }}
            />
            <span>
              <strong>{option.name}</strong> <span className={`badge usage-${option.usage}`}>{option.usage}</span>
              <span className="muted"> · {option.note}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="small ai-key-remember">
        <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
        Remember on this device
      </label>
      <p className="muted small">
        The key stays in this browser and is sent only with AI requests, which this server passes to
        Anthropic without storing it.
        {required && ' Without a key everything else works: globe, site evaluation, comparison and mission analysis.'}
      </p>
    </div>
  )
}
