import type { AlertRaised } from "../../../types/contracts";

/** Persistent, assertive danger-sign banner. Referral only — never diagnosis or treatment. */
export function DangerAlert({ alerts }: { alerts: AlertRaised[] }) {
  if (alerts.length === 0) return null;
  const latest = alerts[alerts.length - 1];
  const labels = [...new Set(alerts.flatMap((a) => a.labels))];
  return (
    <section role="alert" aria-live="assertive" className="enter rounded-2xl border-l-8 border-alarm bg-alarm-wash p-4">
      <h2 className="font-display text-xl font-bold text-alarm">ಅಪಾಯದ ಲಕ್ಷಣ · Danger sign</h2>
      <p className="mt-1 text-lg font-semibold">{latest.message}</p>
      <p className="mt-1 text-sm text-ink-soft">{labels.join(" · ")} — refer to the PHC now.</p>
    </section>
  );
}
