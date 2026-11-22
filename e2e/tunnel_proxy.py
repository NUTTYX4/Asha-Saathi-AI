"""Tunnel proxy QA: the Phase 5 voice suite through the production build and the Caddy demo proxy.

Same disposable asha_saathi_e2e database, api-e2e with MOCK speech and hermetic browser as
e2e/phase5_browser.py, but the browser talks to a second instance of deploy/tunnel (Caddy, serving
frontend/dist) on 127.0.0.1:8081 instead of the Vite dev server. Build first with
VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty (see deploy/tunnel/README.md).

    uv run --no-project --with playwright==1.64.1 python -I e2e/tunnel_proxy.py --channel msedge
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import phase4_browser as p4  # noqa: E402
import phase5_browser as p5  # noqa: E402

PORT = "8081"
WEB = f"http://localhost:{PORT}"
OUT = p4.ROOT / "data" / "e2e" / "tunnel"
COMPOSE = p4.ROOT / "deploy" / "tunnel" / "compose.yaml"
ENV = {**os.environ, "ASHA_TUNNEL_PROJECT": "asha-saathi-tunnel-e2e", "ASHA_UPSTREAM": "api-e2e:8000",
       "ASHA_TUNNEL_PORT": PORT}

p4.WEB = p5.WEB = WEB
p4.OUT = p5.OUT = OUT


def proxy(*args: str) -> None:
    subprocess.run(["docker", "compose", "-f", str(COMPOSE), *args], env=ENV, check=True)


if __name__ == "__main__":
    if not (p4.ROOT / "frontend" / "dist" / "index.html").exists():
        sys.exit("frontend/dist is missing: build the frontend first")
    proxy("up", "-d")
    try:
        code = p5.main()
    finally:
        proxy("down")
    sys.exit(code)
