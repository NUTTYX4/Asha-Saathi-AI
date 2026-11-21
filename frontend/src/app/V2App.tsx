import { useCallback, useEffect, useState } from "react";

import { LoginForm } from "../features/auth/LoginForm";
import { HouseholdWorkspace } from "../features/households/HouseholdWorkspace";
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
    <div className="mx-auto flex min-h-full max-w-6xl flex-col">
      <p
        role="note"
        data-testid="synthetic-banner"
        className="bg-rose px-4 py-1.5 text-center text-xs font-semibold tracking-wide text-white"
      >
        SYNTHETIC DEMO DATA · fictional households and people · map pins are not real residences
      </p>
      <header className="flex items-center justify-between gap-3 bg-ink px-4 py-3 text-white">
        <div>
          <h1 className="font-display text-xl font-bold leading-none">ಆಶಾ ಸಾಥಿ 2.0</h1>
          <p className="text-xs opacity-75">ASHA SAATHI · Household map</p>
        </div>
        {signedIn && (
          <div className="flex items-center gap-2">
            <span className="hidden text-right text-xs sm:block">
              {signedIn.display_name}
              <br />
              <span className="opacity-75">{signedIn.role}</span>
            </span>
            <button type="button" onClick={logout} className="min-h-11 rounded-xl bg-white/15 px-3 text-sm font-semibold">
              Log out
            </button>
          </div>
        )}
      </header>
      <main className="flex-1 px-4 pt-3 pb-10">
        {auth.status === "checking" && <p className="text-sm text-ink-soft">Checking your session…</p>}
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
