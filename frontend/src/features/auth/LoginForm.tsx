import { CircleAlert, Info, LogIn } from "lucide-react";
import { type FormEvent, useState } from "react";

import { ApiError, apiV2 } from "../../lib/apiV2";
import type { MeOut } from "../../types/contracts";
import { BrandMark } from "../ui/BrandMark";
import { Button, Notice } from "../ui/primitives";

interface Props {
  notice: string | null;
  onSignedIn: (me: MeOut) => void;
}

const field =
  "h-12 w-full rounded-md border border-control bg-surface px-3 text-base text-fg hover:border-neutral-700 focus:border-berry-600 focus:outline-none focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#902c4e]";

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
      if (err instanceof ApiError && err.status === 401) setError("Check the username and password, then try again.");
      else if (err instanceof ApiError && err.status === 429) setError("Too many attempts. Wait a few minutes, then try again.");
      else setError(err instanceof ApiError ? err.message : "Sign-in failed. Check the connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6 px-4 pt-8 pb-12 sm:pt-14">
      <div className="flex flex-col gap-3">
        <BrandMark size="lg" />
        <p className="text-lg text-fg-2">
          <span lang="kn" className="block font-bold text-fg">
            ಧ್ವನಿ ಭೇಟಿ ದಾಖಲೆ
          </span>
          Record household visits by voice, for the right person, saved only when you confirm.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-5 rounded-xl border border-line bg-surface p-5 shadow-sm">
        <h2 className="text-xl font-extrabold">Sign in</h2>
        {notice && (
          <Notice tone="info" icon={<Info size={20} />} role="status">
            {notice}
          </Notice>
        )}
        <label className="flex flex-col gap-2 text-sm font-bold">
          Username
          <input
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={field}
          />
        </label>
        <label className="flex flex-col gap-2 text-sm font-bold">
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={field}
          />
        </label>
        {error && (
          <Notice tone="error" icon={<CircleAlert size={20} />} role="alert">
            {error}
          </Notice>
        )}
        <Button type="submit" block disabled={busy} icon={<LogIn size={20} />}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="text-center text-sm text-fg-3">For ASHA workers and supervisors. Synthetic demo accounts only.</p>
    </div>
  );
}
