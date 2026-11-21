import { useEffect, useRef } from "react";

import { formatDate, VISIT_LABEL } from "../../../lib/labels";
import type { VisitRecord } from "../../../types/contracts";
import type { TranscriptLine } from "../hooks/useVoiceSession";
import { Badge } from "../../ui/primitives";

type Row = { key: string; kn: string; en: string; value: string | null };

const STATUS: Record<VisitRecord["status"], { kn: string; en: string; tone: "neutral" | "warning" | "success" }> = {
  draft: { kn: "ಕರಡು", en: "Draft", tone: "neutral" },
  pending_confirmation: { kn: "ದೃಢೀಕರಣ ಬಾಕಿ", en: "To confirm", tone: "warning" },
  confirmed: { kn: "ದೃಢ", en: "Confirmed", tone: "success" },
};

/**
 * The draft visit as a register: one ruled row per field, the version it belongs to, and which
 * required fields are still missing. Values come only from the server's structured record.
 */
export function VisitRecordCard({ record, changedFields }: { record: VisitRecord; changedFields: string[] }) {
  const vaccines =
    record.vaccinations_due === null
      ? null
      : record.vaccinations_due.length
        ? record.vaccinations_due.join(", ")
        : "None due";
  const rows: Row[] = [
    { key: "beneficiary_id", kn: "ವ್ಯಕ್ತಿ", en: "Person", value: record.beneficiary_id },
    {
      key: "visit_type",
      kn: "ಭೇಟಿ ಪ್ರಕಾರ",
      en: "Visit type",
      value: record.visit_type === "unknown" ? null : VISIT_LABEL[record.visit_type].en,
    },
    { key: "weight_kg", kn: "ತೂಕ", en: "Weight", value: record.weight_kg === null ? null : `${record.weight_kg} kg` },
    { key: "vaccinations_due", kn: "ಬಾಕಿ ಲಸಿಕೆ", en: "Vaccinations due", value: vaccines },
    {
      key: "next_visit_date",
      kn: "ಮುಂದಿನ ಭೇಟಿ",
      en: "Next visit",
      value: record.next_visit_date ? formatDate(record.next_visit_date) : null,
    },
  ];
  const status = STATUS[record.status];

  return (
    <section aria-label="Visit record" className="rounded-lg border border-line bg-surface">
      <header className="flex flex-col gap-2 border-b border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <h4 className="text-base font-extrabold">
          <span lang="kn">ಭೇಟಿ ದಾಖಲೆ</span> <span className="font-bold text-fg-2">Visit record</span>
        </h4>
        <span className="flex items-center gap-2">
          <Badge tone="brand">Version {record.record_version}</Badge>
          <Badge tone={status.tone}>{status.en}</Badge>
        </span>
      </header>
      <dl className="divide-y divide-line">
        {rows.map((row) => {
          const missing = record.missing_fields.includes(row.key);
          return (
            <div
              key={`${row.key}-${record.record_version}`}
              className={`grid grid-cols-[minmax(6.5rem,40%)_1fr] items-baseline gap-3 px-4 py-2.5 ${
                changedFields.includes(row.key) ? "v2-field-flash" : ""
              }`}
            >
              <dt className="text-sm">
                <span className="block font-semibold text-fg-2">{row.en}</span>
                <span lang="kn" className="block text-xs text-fg-3">
                  {row.kn}
                </span>
              </dt>
              <dd
                className={`min-w-0 break-words text-lg ${
                  row.value ? "font-bold text-fg" : missing ? "font-bold text-berry-600" : "text-fg-3"
                }`}
              >
                {row.value ?? (missing ? "Needed" : "Not said")}
              </dd>
            </div>
          );
        })}
      </dl>
      {record.requires_phc_referral && (
        <p className="border-t border-error-200 bg-error-50 px-4 py-2.5 text-sm font-bold text-error-700">
          PHC referral flagged on this record (demo rule)
        </p>
      )}
    </section>
  );
}

/** What was said: the worker's final transcripts (right) and the agent's replies (left). */
export function Conversation({ lines }: { lines: TranscriptLine[] }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Scroll inside the feed only, never the page.
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  return (
    <section aria-label="Conversation" className="rounded-lg border border-line bg-surface">
      <h4 className="border-b border-line px-4 py-2.5 text-sm font-bold text-fg-2">
        <span lang="kn">ಮಾತುಕತೆ</span> Conversation
      </h4>
      <div ref={listRef} className="max-h-60 overflow-y-auto px-3 py-3">
        {lines.length === 0 ? (
          <p className="px-1 text-sm text-fg-3">What you say appears here after each pause.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {lines.map((line) => (
              <li
                key={line.id}
                data-who={line.who}
                className={`max-w-[88%] rounded-lg px-3 py-2 text-base leading-relaxed break-words ${
                  line.who === "worker"
                    ? "self-end rounded-br-sm bg-berry-600 text-white"
                    : "self-start rounded-bl-sm bg-sunken text-fg"
                }`}
              >
                <span className="sr-only">{line.who === "worker" ? "You said: " : "ASHA Saathi said: "}</span>
                {line.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
