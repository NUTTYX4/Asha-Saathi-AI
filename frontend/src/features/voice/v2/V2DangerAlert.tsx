import { CircleAlert, UserRound } from "lucide-react";

import type { AlertRaised } from "../../../types/contracts";

/**
 * Danger-sign alert. Shows only the server's guideline message and rule labels, always marked as a
 * demo rule pending clinical review, and never adds advice of its own. Shown the moment the server
 * raises it: an alert is not a saved referral.
 */
export function V2DangerAlert({ alerts }: { alerts: AlertRaised[] }) {
  if (alerts.length === 0) return null;

  return (
    <section role="alert" aria-live="assertive" data-testid="v2-danger-alert" className="flex flex-col gap-2">
      {alerts.map((alert) => (
        <div
          key={`${alert.seq}-${alert.rule_ids.join(",")}`}
          className="v2-rise rounded-lg border border-error-200 border-l-[6px] border-l-error-600 bg-error-50 p-4"
        >
          <div className="flex items-start gap-3">
            <CircleAlert size={24} aria-hidden="true" className="mt-0.5 shrink-0 text-error-600" />
            <div className="min-w-0 flex-1">
              <h4 className="text-lg font-extrabold leading-tight text-error-700">
                <span lang="kn">ಅಪಾಯದ ಲಕ್ಷಣ</span> Danger sign
              </h4>
              <p className="mt-1 text-base font-bold break-words text-fg">{alert.message}</p>
              <p className="mt-1 text-sm break-words text-fg-2">{alert.labels.join("; ")}</p>
              <p className="mt-2 inline-flex rounded-full border border-error-200 bg-surface px-2.5 py-0.5 text-xs font-bold text-error-700">
                Demo only: rules pending clinical review, not a diagnosis
              </p>
              {alert.scope === "other_person" && (
                <p className="mt-2 flex items-start gap-2 rounded-md bg-surface px-3 py-2 text-sm text-fg">
                  <UserRound size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-fg-2" />
                  Heard about someone other than the selected person, so it was not added to this record.
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
