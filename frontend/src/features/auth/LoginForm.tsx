import { type FormEvent, useState } from "react";

import { ApiError, apiV2 } from "../../lib/apiV2";
import type { MeOut } from "../../types/contracts";

interface Props {
  notice: string | null;
  onSignedIn: (me: MeOut) => void;
}

/** Sign-in with the existing V2 session cookie (Phase 2). The password lives only in this form. */
export function LoginForm({ notice, onSignedIn }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await apiV2.login({ username: username.trim(), password });
      setPassword("");
      onSignedIn(me);
    } catch (err) {
      setPassword("");
      if (err instanceof ApiError && err.status === 401) setError("Invalid username or password.");
      else if (err instanceof ApiError && err.status === 429) setError("Too many failed attempts. Wait a few minutes.");
      else setError(err instanceof ApiError ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto mt-6 flex w-full max-w-sm flex-col gap-4 rounded-2xl bg-sheet p-5 shadow-sm">
      <h2 className="font-display text-xl font-bold">Sign in</h2>
      {notice && (
        <p role="status" className="rounded-xl bg-paper px-3 py-2 text-sm text-ink-soft">
          {notice}
        </p>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Username
        <input
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="min-h-12 rounded-xl border border-rule px-3 text-base font-normal"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Password
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="min-h-12 rounded-xl border border-rule px-3 text-base font-normal"
        />
      </label>
      {error && (
        <p role="alert" className="rounded-xl bg-alarm-wash px-3 py-2 text-sm text-alarm">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="min-h-12 rounded-xl bg-ink font-semibold text-white disabled:opacity-60"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
