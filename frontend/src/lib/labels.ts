import type { SessionState, VisitType } from "../types/contracts";

/** Kannada-first UI labels (PENDING native-speaker review), English as secondary. */

export const STATE_LABEL: Record<SessionState, { kn: string; en: string }> = {
  idle: { kn: "ಸಿದ್ಧ", en: "Ready" },
  listening: { kn: "ಕೇಳುತ್ತಿದ್ದೇನೆ", en: "Listening" },
  transcribing: { kn: "ಬರೆಯುತ್ತಿದ್ದೇನೆ", en: "Transcribing" },
  processing: { kn: "ಪರಿಶೀಲಿಸುತ್ತಿದ್ದೇನೆ", en: "Processing" },
  clarifying: { kn: "ಒಂದು ಪ್ರಶ್ನೆ", en: "Asking" },
  reading_back: { kn: "ಓದುತ್ತಿದ್ದೇನೆ", en: "Reading back" },
  awaiting_confirmation: { kn: "ದೃಢೀಕರಣಕ್ಕೆ ಕಾಯುತ್ತಿದೆ", en: "Awaiting confirmation" },
  confirmed: { kn: "ದೃಢಪಡಿಸಲಾಗಿದೆ", en: "Confirmed" },
  saved: { kn: "ಉಳಿಸಲಾಗಿದೆ", en: "Saved" },
  error: { kn: "ದೋಷ", en: "Error" },
};

export const VISIT_LABEL: Record<VisitType, { kn: string; en: string }> = {
  ANC: { kn: "ಗರ್ಭಿಣಿ ಭೇಟಿ", en: "ANC" },
  PNC: { kn: "ಹೆರಿಗೆ ನಂತರ", en: "PNC" },
  newborn: { kn: "ನವಜಾತ ಶಿಶು", en: "Newborn" },
  immunisation: { kn: "ಲಸಿಕೆ", en: "Immunisation" },
  unknown: { kn: "—", en: "Not given" },
};

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
