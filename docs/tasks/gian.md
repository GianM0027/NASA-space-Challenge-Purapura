<!-- ABOUTME: Task file of Gian: contracts, AI, mission analysis, API and frontend; status, next, blockers -->
<!-- ABOUTME: Only Gian (and Gian's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Gian: tasks

## Status
Bootstrap pushed: contracts, examples, rules. Nothing implemented yet.

## Next (in priority order)
1. C3 (LLM JSON check): Claude Code CLI headless returns schema-valid `MissionRequirements`; decide model and provider (D18, LLM provider).
2. C4 (map tiles check): install Node.js LTS (not present on this PC), scaffold `frontend/` (Vite React TS), render Moon Trek tiles in OpenLayers, global and polar.
3. API skeleton (IF-4, REST API) serving `data/examples/*.json` so the frontend works from hour one; `.env.example`.
4. UI-1 (map with sites), UI-2 (site panel with timeline and time to sunset/Earthset), UI-4 (AI box).
5. AI-1 (request to requirements), AI-2 (deterministic ranking), AI-3 (no invented numbers), AI-4 (swappable provider).
6. UI-3 (side-by-side comparison).
7. MA-1 (date-slip sweep), MA-2 (dispersion), MA-3 (summary), UI-5 (mission analysis view), AI-6 (AI presents it).
8. UI-6 (data attribution), then P2 items if time remains.

## Done

## Blockers

## Requests
