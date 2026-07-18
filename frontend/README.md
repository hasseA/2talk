# 2talk frontend

React and TypeScript frontend for the two-participant 2talk hackathon flow,
powered by Vite. It supports conversation creation and joining, short-polling
message updates, private guidance, retrying failed outgoing messages, and
ending a conversation.

For local frontend-only development, install dependencies with `npm install`
and start Vite with `npm run dev`. The application expects the backend API via
Vite's `/api` proxy; the repository root README documents the complete Docker
Compose workflow.

Run frontend verification with:

```powershell
npx playwright install chromium
npm run typecheck
npm test
npm run build
npm audit
```

The current release does not include conversation summaries, SSE, or
WebSockets.
