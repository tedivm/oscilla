## ADDED Requirements

### Requirement: Vite dev server supports `HMR_CLIENT_PORT` environment variable override

`frontend/vite.config.ts` SHALL read the `HMR_CLIENT_PORT` environment variable and pass it to `server.hmr.clientPort`. When unset, the value SHALL be `undefined`, which causes Vite to use its default HMR port behavior (connecting on the same port as the dev server).

This allows the Vite dev server to operate correctly behind a reverse proxy on a different port (e.g. Caddy on port 80) without any change to developer workflow when running Vite directly outside Docker.

#### Scenario: HMR connects via proxy port when `HMR_CLIENT_PORT` is set

- **GIVEN** the `frontend` container has `HMR_CLIENT_PORT=80` in its environment
- **WHEN** a browser loads the app through the gateway on port 80
- **THEN** the Vite HMR WebSocket client connects to `ws://localhost:80` (not port 5173)
- **AND** hot module replacement works through the gateway

#### Scenario: HMR uses Vite default when `HMR_CLIENT_PORT` is unset

- **GIVEN** `HMR_CLIENT_PORT` is not set in the environment (local non-Docker dev)
- **WHEN** `vite dev` starts
- **THEN** `server.hmr.clientPort` is `undefined` and Vite's default HMR behavior is used
- **AND** HMR connects on the same port as the dev server (5173)
