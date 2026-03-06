# PWA Rollback Analysis (White Screen)

## Why yesterday's build failed
1. A full React/Vite/Tailwind/PWA scaffold was added directly into the existing Python desktop repo in one step without a verified local frontend dependency install/build run in this environment.
2. The frontend scaffold introduced new runtime/build entrypoints (`index.html`, `src/main.tsx`, Vite config, Tailwind/PostCSS config, package manifest) that were not part of the previously working desktop game runtime.
3. Because this scaffold was not validated end-to-end before merge, it created a high-risk integration state for local host startup (including blank/white screen symptoms when frontend boot fails).

## What was removed
To restore the previously working game baseline, all newly introduced frontend/PWA scaffold files were removed from this branch:
- Vite/Tailwind/TypeScript configs
- React app source tree under `src/`
- PWA icons and PWA readme
- frontend package manifest and html entrypoint

## Current status
- Python desktop app/game code remains intact.
- Existing Python tests compile and pass.
- Repo is now back to the non-PWA baseline so GUI/PWA integration can be reintroduced in a controlled step tomorrow.
