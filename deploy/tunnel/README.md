# Full-stack demo link (Cloudflare quick tunnel)

This gives one HTTPS link to the working app running on this laptop. Use it to demo from a phone on mobile data or to share with a reviewer.

```
browser ──HTTPS──▶ Cloudflare ──tunnel──▶ cloudflared (this laptop)
        ──▶ Caddy 127.0.0.1:8080 (deploy/tunnel)
              ├─ /v2, /assets/*  production build (frontend/dist)
              ├─ /api/v2/*, /api/health, /ws/v2/session  ──▶ api container (unchanged)
              └─ any other /api, /ws path ─▶ 404     / ─▶ redirect to /v2
```

- Caddy passes the browser's Host header through unchanged. So the backend's own checks keep working:
  - the httpOnly, Secure, SameSite=Strict session cookie
  - the anti-CSRF header
  - the same-origin check on the voice socket
  - territory scoping
  - the exactly-once save
- Nothing in the backend, database or Docker stack is changed. Caddy is a separate Compose project that only joins the stack's `egress` network.
- FastAPI `/docs` and `/openapi.json` are not forwarded.

## Start

Run these from the repository root in PowerShell.

1. Check the backend:
   ```powershell
   docker compose ps                     # api and db (healthy); start with: docker compose up -d
   ```
2. Build the frontend once, with the OpenFreeMap style built in:
   ```powershell
   cd frontend
   $env:VITE_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
   npm run build
   Remove-Item Env:VITE_MAP_STYLE_URL
   cd ..
   ```
3. Start the demo proxy:
   ```powershell
   docker compose -f deploy/tunnel/compose.yaml up -d
   ```
4. Start the tunnel and keep this window open:
   ```powershell
   cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8080
   ```
   The link is printed as `https://<random-words>.trycloudflare.com`. If it shows Cloudflare error 1016 at first, wait a few seconds.

To require an email one-time PIN before anyone reaches the app, add `--allowed-mail "you@example.com,friend@example.com"` to the tunnel command. That is recommended whenever the link is shared beyond yourself.

## Stop

1. Press Ctrl+C in the cloudflared window. The link dies immediately and a new start gives a new link.
2. Stop the proxy:
   ```powershell
   docker compose -f deploy/tunnel/compose.yaml down
   ```
   This touches only the proxy, never the api or db.

## Things to know

- **Who can get in.** Without `--allowed-mail`, anyone with the link sees the sign-in page. They can do nothing more without a demo account and its password, so use strong demo passwords:
  ```powershell
  docker compose exec api python -m scripts.set_password --username demo_worker_a
  ```
- **Voice is live.** The demo stack uses real Gnani speech: every voice visit spends credits. Mock speech exists only for the disposable e2e database (`e2e/tunnel_proxy.py` runs the voice suite through this proxy with mock speech).
- **Login rate limit.** Behind the proxy every visitor shares one client address. Repeated wrong passwords for an account lock that account for everyone for the limiter window.
- **Quick tunnel limits.** No uptime guarantee and a new hostname on every start. For a stable address, use a named tunnel on a domain in a Cloudflare account, protected with Cloudflare Access.
