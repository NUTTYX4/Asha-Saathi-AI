import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import { formatDate, VISIT_LABEL } from "../../lib/labels";
import type { FollowUpItem, SavedVisit } from "../../types/contracts";

/** Follow-up list (referrals first, then by due date) and saved visits, from the backend. */
export function FollowUpsPage({ refreshKey }: { refreshKey: number }) {
  const [followups, setFollowups] = useState<FollowUpItem[] | null>(null);
  const [visits, setVisits] = useState<SavedVisit[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.followups(), api.visits()])
      .then(([f, v]) => {
        setFollowups(f);
        setVisits(v);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [refreshKey]);

  if (error) return <p className="rounded-2xl bg-alarm-wash p-4 text-alarm">ಲೋಡ್ ವಿಫಲ · {error}</p>;
  if (!followups) return <p className="p-4 text-ink-soft">ಲೋಡ್ ಆಗುತ್ತಿದೆ…</p>;

  return (
    <div className="flex flex-col gap-5">
      <section>
        <h2 className="font-display text-xl font-bold">ಮುಂದಿನ ಕೆಲಸ · Follow-ups</h2>
        {followups.length === 0 ? (
          <p className="mt-2 text-ink-soft">ಇನ್ನೂ ಏನೂ ಇಲ್ಲ · Nothing yet</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {followups.map((f) => (
              <li
                key={f.visit_id}
                className={`rounded-2xl bg-sheet p-3 ring-1 ${f.requires_phc_referral ? "ring-2 ring-alarm" : "ring-rule"}`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-display text-lg font-bold">ID {f.beneficiary_id}</span>
                  <span className="font-semibold">{formatDate(f.due_date)}</span>
                </div>
                <div className="text-sm text-ink-soft">
                  {VISIT_LABEL[f.visit_type].kn} · {VISIT_LABEL[f.visit_type].en}
                  {f.vaccinations_due?.length ? ` · ${f.vaccinations_due.join(", ")}` : ""}
                </div>
                {f.requires_phc_referral && (
                  <div className="mt-1 text-sm font-semibold text-alarm">⚠ PHC ರೆಫರಲ್ · {f.danger_signs.join(", ")}</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2 className="font-display text-xl font-bold">ಉಳಿಸಿದ ಭೇಟಿಗಳು · Saved visits</h2>
        <ul className="mt-2 flex flex-col">
          {visits.map((v) => (
            <li key={v.id} className="register-row flex justify-between gap-3 py-2">
              <span>
                <strong>ID {v.beneficiary_id}</strong> · {VISIT_LABEL[v.visit_type].en}
                {v.weight_kg !== null ? ` · ${v.weight_kg} kg` : ""}
              </span>
              <span className="text-sm text-ink-soft">#{v.id}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
