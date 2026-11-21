import "@fontsource-variable/mulish/wght.css";
import "@fontsource-variable/noto-sans-kannada/wght.css";

import { Info, LogOut } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LoginForm } from "../features/auth/LoginForm";
import { HouseholdWorkspace } from "../features/households/HouseholdWorkspace";
import { BrandMark } from "../features/ui/BrandMark";
import { Button } from "../features/ui/primitives";
import { ApiError, apiV2, isUnauthorized } from "../lib/apiV2";
import type { MeOut } from "../types/contracts";

type Auth =
  | { status: "checking" }
  | { status: "signed_out"; notice: string | null }
  | { status: "signed_in"; me: MeOut };

const HEARTBEAT_MS = 60_000;
const SESSION_ENDED = "Your session has ended. Please sign in again.";

/** Grants, as a key: a change of territories remounts the workspace and clears any selection. */
function accessKey(me: MeOut): string {
  return `${me.user_id}:${me.role}:${me.territories.map((t) => t.id).sort().join(",")}`;
}

/**
 * ASHA SAATHI 2.0 browser app at /v2 (Phase 4–5: household map, member selection and voice visit).
 * Uses the Phase 2 session cookie; the Round 1 voice screen at / is unchanged.
 */
export default function V2App() {
  useEffect(() => {
    const meta = document.querySelector('meta[name="theme-color"]');
    const previous = meta?.getAttribute("content") ?? null;
    meta?.setAttribute("content", "#ffffff");
    document.title = "ಆಶಾ ಸಾಥಿ 2.0 · ASHA Saathi";
    return () => {
      if (meta && previous) meta.setAttribute("content", previous);
    };
  }, []);
  const [auth, setAuth] = useState<Auth>({ status: "checking" });
  const sessionLost = useCallback((notice: string) => setAuth({ status: "signed_out", notice }), []);

  useEffect(() => {
    let alive = true;
    apiV2
      .me()
      .then((me) => alive && setAuth({ status: "signed_in", me }))
      .catch((e) => {
        if (!alive) return;
        setAuth({ status: "signed_out", notice: isUnauthorized(e) ? null : e instanceof ApiError ? e.message : null });
      });
    return () => {
      alive = false;
    };
  }, []);

  // While signed in, re-check the session every minute and whenever the tab becomes visible, so
  // an expired, revoked or re-scoped session clears the selection even if the worker is idle.
  const signedIn = auth.status === "signed_in" ? auth.me : null;
  const currentKey = signedIn ? accessKey(signedIn) : null;
  useEffect(() => {
    if (!currentKey) return;
    const check = () =>
      apiV2
        .me()
        .then((me) => {
          if (accessKey(me) !== currentKey) setAuth({ status: "signed_in", me });
        })
        .catch((e) => {
          if (isUnauthorized(e)) sessionLost(SESSION_ENDED);
        });
    const timer = window.setInterval(check, HEARTBEAT_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void check();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [currentKey, sessionLost]);

  async function logout() {
    let notice = "You have signed out.";
    try {
      await apiV2.logout();
    } catch (e) {
      // 401: the session was already gone. Anything else: the server may still hold it.
      if (!isUnauthorized(e)) {
        notice =
          "Could not reach the server to end your session, so this device may still be signed in. " +
          "Reconnect, then sign in and log out again.";
      }
    }
    setAuth({ status: "signed_out", notice }); // local state is cleared either way
  }

  return (
    <div className="v2 flex min-h-full flex-col">
      <p
        role="note"
        data-testid="synthetic-banner"
        className="flex items-center justify-center gap-2 border-b border-berry-100 bg-berry-50 px-4 py-1.5 text-center text-xs font-semibold text-berry-700"
      >
        <Info size={14} aria-hidden="true" className="shrink-0" />
        Synthetic demo data: fictional households and people. Map pins are not real residences.
      </p>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex min-h-14 max-w-7xl items-center justify-between gap-3 px-4 py-2 sm:px-6">
          <BrandMark />
          {signedIn && (
            <div className="flex items-center gap-2">
              <span className="hidden items-center gap-2 sm:flex">
                <span
                  aria-hidden="true"
                  data-initials={signedIn.display_name
                    .split(/\s+/)
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((w) => w[0])
                    .join("")
                    .toUpperCase()}
                  className="v2-avatar grid size-9 place-items-center rounded-full bg-berry-100 text-sm font-extrabold text-berry-700"
                />
                <span className="flex flex-col text-right leading-tight">
                  <span className="text-sm font-bold">{signedIn.display_name}</span>
                  <span className="text-xs text-fg-2">
                    {ROLE_LABEL[signedIn.role]}
                    {signedIn.territories.length > 0 && `, ${signedIn.territories.map((t) => t.code).join(" and ")}`}
                  </span>
                </span>
              </span>
              <Button variant="ghost" size="md" onClick={logout} icon={<LogOut size={18} />}>
                Log out
              </Button>
            </div>
          )}
        </div>
      </header>
      <main className="flex-1">
        {auth.status === "checking" && (
          <p role="status" className="px-4 py-10 text-center text-fg-2">
            Checking your session…
          </p>
        )}
        {auth.status === "signed_out" && (
          <LoginForm notice={auth.notice} onSignedIn={(me) => setAuth({ status: "signed_in", me })} />
        )}
        {auth.status === "signed_in" && (
          <HouseholdWorkspace key={accessKey(auth.me)} me={auth.me} onSessionLost={sessionLost} />
        )}
      </main>
    </div>
  );
}

const ROLE_LABEL: Record<MeOut["role"], string> = {
  worker: "ASHA worker",
  supervisor: "Supervisor (read-only)",
  admin: "Administrator",
};
