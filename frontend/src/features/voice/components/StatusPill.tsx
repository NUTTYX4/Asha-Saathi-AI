import { STATE_LABEL } from "../../../lib/labels";
import type { SessionState } from "../../../types/contracts";

interface Props {
  state: SessionState;
  agentSpeaking: boolean;
}

export function StatusPill({ state, agentSpeaking }: Props) {
  const label = agentSpeaking ? { kn: "ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ", en: "Speaking" } : STATE_LABEL[state];
  const tone =
    state === "error" ? "bg-alarm text-white" : agentSpeaking ? "bg-ink text-white" : state === "saved" ? "bg-leaf text-white" : "bg-sheet text-ink";
  return (
    <div role="status" aria-live="polite" className={`inline-flex items-baseline gap-2 rounded-full px-4 py-1.5 ring-1 ring-rule ${tone}`}>
      <span className="font-display text-lg font-medium">{label.kn}</span>
      <span className="text-sm opacity-80">{label.en}</span>
    </div>
  );
}
