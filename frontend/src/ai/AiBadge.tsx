// ABOUTME: The "AI" badge: a small circle shown before any text the AI wrote (comments, reasons)
// ABOUTME: Owner: Gian. One component for the whole app, so AI text always looks the same

/** A small "AI" circle; its tooltip says the numbers in the text are checked against the engine. */
export function AiBadge() {
  return (
    <span className="ai-badge" title="Written by the AI; every number in it is checked against the engine" aria-label="AI">
      AI
    </span>
  )
}
