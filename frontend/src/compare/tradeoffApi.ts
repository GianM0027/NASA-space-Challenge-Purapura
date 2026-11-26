// ABOUTME: Trade-off calls of the comparison view: POST /api/tradeoff and the Excel export download
// ABOUTME: Owner: Federico (D37). Kept here until Gian moves them into api/client.ts (his file)

import { aiKeyHeaders } from '../api/aiKey'
import { ApiError } from '../api/client'
import type { TradeoffRequest, TradeoffResult } from '../api/contracts'

async function post(path: string, body: TradeoffRequest): Promise<Response> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      // The visitor's own API key, if saved, writes the AI comment of the result (decision D43).
      headers: { 'Content-Type': 'application/json', ...aiKeyHeaders() },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('Backend unreachable: is it running on port 8000 (README, Run)?')
  }
  if (!response.ok) {
    const text = await response.text()
    let detail = text
    try {
      const parsed: unknown = JSON.parse(text)
      if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
        detail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail)
      }
    } catch {
      // Not JSON: keep the raw text.
    }
    throw new ApiError(path, response.status, detail)
  }
  return response
}

/** Run the trade-off: the backend evaluates the scenarios and scores them. */
export async function runTradeoff(body: TradeoffRequest): Promise<TradeoffResult> {
  return (await (await post('/api/tradeoff', body)).json()) as TradeoffResult
}

/** Download the live Excel workbook of the same trade-off. */
export async function downloadTradeoff(body: TradeoffRequest, filename: string): Promise<void> {
  const blob = await (await post('/api/tradeoff/export', body)).blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
