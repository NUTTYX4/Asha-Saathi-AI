import type { AlertRaised } from "../../../types/contracts";

/**
 * V2 danger-sign alert banner. Shows only the server's guideline message and labels, explicitly
 * marked as demo-only pending clinical review and never adding unapproved clinical guidance.
 */
export function V2DangerAlert({ alerts }: { alerts: AlertRaised[] }) {
  if (alerts.length === 0) return null;

  return (
    <section
      role="alert"
      aria-live="assertive"
      data-testid="v2-danger-alert"
      className="flex flex-col gap-2"
    >
      {alerts.map((alert) => (
        <div
          key={`${alert.seq}-${alert.rule_ids.join(",")}`}
          className="enter rounded-2xl border-l-8 border-alarm bg-alarm-wash p-3 text-ink"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-display text-base font-bold text-alarm">
              ಅಪಾಯದ ಲಕ್ಷಣ · Danger sign
            </h3>
            <span className="rounded-full border border-alarm/30 bg-sheet px-2 py-0.5 text-[11px] font-semibold text-alarm">
              Demo only · rules pending clinical review · not a diagnosis
            </span>
          </div>
          <p className="mt-1 text-base font-semibold break-words">{alert.message}</p>
          <p className="mt-1 text-xs text-ink-soft break-words">{alert.labels.join(" · ")}</p>
          {alert.scope === "other_person" && (
            <p className="mt-1.5 rounded-lg bg-sheet px-2.5 py-1.5 text-xs font-medium text-ink">
              Heard about someone other than the selected person, so it was not added to this record.
            </p>
          )}
        </div>
      ))}
    </section>
  );
}
