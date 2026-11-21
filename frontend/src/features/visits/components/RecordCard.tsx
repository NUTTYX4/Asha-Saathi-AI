import { formatDate, VISIT_LABEL } from "../../../lib/labels";
import type { VisitRecord } from "../../../types/contracts";

interface Props {
  record: VisitRecord;
  changedFields: string[];
}

type Row = { key: string; kn: string; en: string; value: string | null };

/** The visit as a register sheet: one ruled row per field; missing fields marked. */
export function RecordCard({ record, changedFields }: Props) {
  const vaccines =
    record.vaccinations_due === null ? null : record.vaccinations_due.length ? record.vaccinations_due.join(", ") : "ಇಲ್ಲ · None";
  const rows: Row[] = [
    { key: "beneficiary_id", kn: "ಫಲಾನುಭವಿ ಐಡಿ", en: "Beneficiary ID", value: record.beneficiary_id },
    {
      key: "visit_type",
      kn: "ಭೇಟಿ ಪ್ರಕಾರ",
      en: "Visit type",
      value: record.visit_type === "unknown" ? null : `${VISIT_LABEL[record.visit_type].kn} · ${VISIT_LABEL[record.visit_type].en}`,
    },
    { key: "weight_kg", kn: "ತೂಕ", en: "Weight", value: record.weight_kg === null ? null : `${record.weight_kg} kg` },
    { key: "vaccinations_due", kn: "ಬಾಕಿ ಲಸಿಕೆ", en: "Vaccinations due", value: vaccines },
    { key: "next_visit_date", kn: "ಮುಂದಿನ ಭೇಟಿ", en: "Next visit", value: record.next_visit_date ? formatDate(record.next_visit_date) : null },
  ];

  return (
    <section aria-label="Visit record" className="rounded-2xl bg-sheet px-4 pt-3 pb-1 ring-1 ring-rule">
      <header className="flex items-baseline justify-between pb-2">
        <h2 className="font-display text-xl font-bold">ಭೇಟಿ ದಾಖಲೆ</h2>
        <span className="text-sm text-ink-soft">
          v{record.record_version} · {record.status === "pending_confirmation" ? "ದೃಢೀಕರಣ ಬಾಕಿ" : record.status === "confirmed" ? "ದೃಢ" : "ಕರಡು"}
        </span>
      </header>
      <dl>
        {rows.map((row) => {
          const missing = record.missing_fields.includes(row.key);
          return (
            <div
              key={`${row.key}-${record.record_version}`}
              className={`register-row grid grid-cols-[8.5rem_1fr] items-baseline gap-3 py-2.5 ${
                changedFields.includes(row.key) ? "field-flash" : ""
              }`}
            >
              <dt>
                <span className="block font-medium">{row.kn}</span>
                <span className="block text-xs text-ink-soft">{row.en}</span>
              </dt>
              <dd className={`text-lg ${row.value ? "font-semibold" : missing ? "text-rose" : "text-ink-soft"}`}>
                {row.value ?? (missing ? "ಬೇಕು · needed" : "—")}
              </dd>
            </div>
          );
        })}
      </dl>
      {record.requires_phc_referral && (
        <p className="py-2.5 font-semibold text-alarm">⚠ PHC ರೆಫರಲ್ ಅಗತ್ಯ · PHC referral required</p>
      )}
    </section>
  );
}
