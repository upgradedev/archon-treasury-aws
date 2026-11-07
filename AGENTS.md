# Redesign architecture

- Keep the React/Vite frontend and Python treasury backend separate; port visual design without changing backend contracts.
- Share navigation definitions and use URL hash state for task views, so deep links and browser history work without changing legacy server routing.
- Use same-origin API requests with the existing session cookie and surface service errors; financial decisions remain server-side.
- Keep visual role colors in frontend/src/index.css and reusable control variants, so design changes cannot affect treasury logic.
- Preserve the Python-served interface and existing AWS packaging until a separately approved React hosting cutover.
- Keep production continuation instructions and verified checks in docs/ANTIGRAVITY_HANDOFF.md and docs/REDESIGN_VERIFICATION.md.
