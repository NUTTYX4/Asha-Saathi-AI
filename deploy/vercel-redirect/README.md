# Permanent demo address

**https://novix-asha-saathi-demo.vercel.app** never changes. Share this one.

It is a dedicated Vercel project, `novix-asha-saathi-demo`, that holds only a redirect (HTTP 307, not cached) to the current Cloudflare quick tunnel:

| Visitor opens | Sent to |
| --- | --- |
| `/` | `<tunnel>/v2` |
| `/<anything>` | `<tunnel>/<anything>` |

## When the tunnel address changes

1. Start a new tunnel (see `deploy/tunnel/README.md`) and copy its `https://….trycloudflare.com` address.
2. From the repository root in PowerShell, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\deploy\vercel-redirect\set-demo-link.ps1 https://NEW-ADDRESS.trycloudflare.com
   ```

The script:

- refuses to switch if the new tunnel's `/api/health` does not answer, so the permanent link is never pointed at a dead tunnel;
- writes `vercel.json` and deploys it to production of this project, in about 20 seconds;
- prints where the permanent address now points.

## Things to know

- **Why a redirect.** Proxying through Vercel would break the voice WebSocket, which Vercel does not proxy. The address bar therefore shows the tunnel address after the redirect. Viewers should always open the Vercel link, not a bookmarked tunnel address.
- **Sign in again after a switch.** Sign-in cookies belong to the tunnel address, so viewers sign in again after a switch.
- **No Git connection.** The project is not connected to Git: pushes never change it. Only this script does.
- **Main address stays public.** It has Vercel's Standard protection, so its main `.vercel.app` address is public. Generated per-deployment URLs require a Vercel login.
- **The frontend preview is separate.** The original project `novix-asha-saathi` (the frontend preview, protected) is untouched by this.
- **Requirement.** The Vercel CLI must be signed in on this laptop (`npx vercel whoami`). If it is not, run `npx vercel login`.
