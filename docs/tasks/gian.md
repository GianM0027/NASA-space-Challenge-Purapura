<!-- ABOUTME: Task file of Gian: contracts, AI, mission analysis, API and frontend; status, next, blockers -->
<!-- ABOUTME: Only Gian (and Gian's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Gian: tasks

## Status
API skeleton serves every IF-4 (REST API) endpoint from the example payloads; frontend scaffold
(Vite, React, TypeScript, OpenLayers) talks to it through the dev proxy.

## Next (in priority order)
1. C3 (LLM JSON check): Claude Code CLI headless returns schema-valid `MissionRequirements`; decide model and provider (D18, LLM provider).
2. C4 (map tiles check): render Moon Trek tiles in OpenLayers, global and polar.
3. TypeScript types for the contracts (generated from the Pydantic JSON schema).
4. UI-1 (map with sites), UI-2 (site panel with timeline and time to sunset/Earthset), UI-4 (AI box).
5. AI-1 (request to requirements), AI-2 (deterministic ranking), AI-3 (no invented numbers), AI-4 (swappable provider).
6. UI-3 (side-by-side comparison).
7. MA-1 (date-slip sweep), MA-2 (dispersion), MA-3 (summary), UI-5 (mission analysis view), AI-6 (AI presents it).
8. UI-6 (data attribution), then P2 items if time remains.

## Done
- API skeleton (IF-4, REST API) on example services, 11 smoke tests; frontend scaffold with `/api` proxy, verified end to end in the browser.
- Node.js LTS installed on this PC.
- Minor: Starlette warns that `httpx` with its TestClient is deprecated in favour of `httpx2`; switch after verifying the `httpx2` package.

## Blockers

## Requests
