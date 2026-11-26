// ABOUTME: The one close control of every floating window (AI box, mission analysis, comparison, report)
// ABOUTME: Owner: Gian. An × icon; closing keeps the window's work, reopened from its button in the dock

/** Square × button; `what` names the window for screen readers ("Close the AI assistant"). */
export function CloseButton(props: { what: string; onClick: () => void; hint?: string }) {
  const { what, onClick, hint = 'your work is kept' } = props
  return (
    <button className="close-button" aria-label={`Close ${what}`} title={`Close (${hint})`} onClick={onClick}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        <path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </button>
  )
}
