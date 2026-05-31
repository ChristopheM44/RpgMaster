# RpgMaster - Copilot Instructions

When assisting a developer with RpgMaster, keep these core architectural decisions and environments anchored.

---

## Ollama Cloud & Gemma 4 Integration
*   **Target API**: Remote API hosted on `https://ollama.com` via `OLLAMA_BASE_URL`.
*   **Model**: `gemma4:31b` (tagged `cloud`).
*   **Authentication**: Secure bearer tokens using `OLLAMA_API_KEY` sent via `Authorization: Bearer <key>`.
*   **Timeout Policy**: 3.0s connect timeout (quick network failure detection) and 240.0s read timeout (to accommodate Gemma 4 generation delays).
*   **Fail-soft Narration**: If Ollama goes down or times out, the backend serves `_FALLBACK_NARRATION` and pushes a friendly error event to the user's interface using WebSockets, rather than raising exceptions that halt the server.

---

## Tech Stack
*   **Backend**: Python 3.11+ / FastAPI (fully asynchronous).
*   **Frontend**: Vue.js 3 / TypeScript (using `<script setup lang="ts">` and Composition API).
*   **Styling**: TailwindCSS v4 with design tokens mapped in `src/assets/main.css`.
*   **Database**: SQLite via SQLAlchemy async (`aiosqlite`) + Alembic migrations.

---

## Architectural Rules
1.  **Pure Rules Engine**: Code in `backend/app/engine/` is completely synchronous and pure (zero I/O, no DB access, no network calls). The rules engine resolves mechanics (dice, HP, initiative); LLMs only generate narrative styling based on engine outputs.
2.  **No New SQL Tables**: The session state is modeled and persisted as a structured JSON blob in `Campaign.dossier` validated using Pydantic.
3.  **Voice Router Fallbacks**: Voxtral 4B TTS (on port 8091) and Kokoro-ONNX are supported under local mode. Ensure that OpenAI Realtime audio failures gracefully fall back to local Kokoro/Voxtral providers with zero user disruption.
4.  **No Key Leakage**: Never expose API keys (`OLLAMA_API_KEY` or `OPENAI_REALTIME_API_KEY`) to the frontend.
