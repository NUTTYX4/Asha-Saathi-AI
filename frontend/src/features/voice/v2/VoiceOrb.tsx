import { Check, Loader2, Mic, MicOff, ShieldCheck, Volume2 } from "lucide-react";

import type { VoiceVisitState } from "./voiceVisit";
import { canConfirm } from "./voiceVisit";

type OrbKind = "connecting" | "disclosure" | "blocked" | "speak" | "hearing" | "working" | "agent" | "readback" | "ready" | "saving";

interface OrbView {
  kind: OrbKind;
  kn: string;
  en: string;
  hint: string;
}

/** What the worker should do right now, derived only from the live session state. */
export function orbView(s: VoiceVisitState): OrbView {
  if (s.phase === "connecting") {
    return { kind: "connecting", kn: "ಸಂಪರ್ಕಿಸಲಾಗುತ್ತಿದೆ", en: "Connecting", hint: "Opening a secure voice session for this person." };
  }
  if (s.phase === "saving") {
    return { kind: "saving", kn: "ಉಳಿಸಲಾಗುತ್ತಿದೆ", en: "Saving", hint: "Saving the confirmed version. Keep this screen open." };
  }
  if (s.disclosureFailed) {
    return { kind: "blocked", kn: "ಮೈಕ್ ಆಫ್", en: "Microphone off", hint: "The AI disclosure did not play. Cancel and start again." };
  }
  if (!s.disclosurePlayed) {
    return { kind: "disclosure", kn: "ಮೊದಲು ಕೇಳಿ", en: "Listen first", hint: "The AI disclosure is playing. The microphone opens when it ends." };
  }
  if (canConfirm(s)) {
    return { kind: "ready", kn: "ಪರಿಶೀಲಿಸಿ ಮತ್ತು ದೃಢೀಕರಿಸಿ", en: "Check, then confirm", hint: "Speak to correct a field. Saying ಹೌದು does not save: press Confirm and Save." };
  }
  const readbackPending =
    s.confirmVersion !== null && s.playedReadbackVersion !== s.confirmVersion && !s.readbackAudioFailed;
  if (s.agentSpeaking && readbackPending) {
    return { kind: "readback", kn: "ಓದುತ್ತಿದ್ದೇನೆ", en: "Reading back", hint: "Listen to the whole read-back before confirming." };
  }
  if (s.agentSpeaking) {
    return { kind: "agent", kn: "ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ", en: "Speaking", hint: "Listen, then answer." };
  }
  if (s.speechInProgress || s.sessionState === "transcribing") {
    return { kind: "hearing", kn: "ಕೇಳಿಸಿಕೊಳ್ಳುತ್ತಿದ್ದೇನೆ", en: "Hearing you", hint: "Keep talking. A short pause ends the note." };
  }
  if (s.sessionState === "processing") {
    return { kind: "working", kn: "ದಾಖಲೆ ತಯಾರಾಗುತ್ತಿದೆ", en: "Updating the record", hint: "Reading what you said into the visit record." };
  }
  return { kind: "speak", kn: "ಮಾತನಾಡಿ", en: "Speak now", hint: "Describe the visit in Kannada or English." };
}

const ORB_STYLE: Record<OrbKind, string> = {
  connecting: "bg-neutral-100 text-fg-2",
  disclosure: "bg-info-50 text-info-700 ring-4 ring-info-200",
  blocked: "bg-error-50 text-error-600 ring-4 ring-error-200",
  speak: "bg-lime-300 text-on-accent v2-orb-listening",
  hearing: "bg-berry-600 text-white ring-8 ring-berry-100",
  working: "bg-berry-50 text-berry-700 ring-4 ring-berry-100",
  agent: "bg-info-50 text-info-700 ring-4 ring-info-200",
  readback: "bg-info-600 text-white ring-8 ring-info-50",
  ready: "bg-lime-300 text-on-accent ring-8 ring-lime-100",
  saving: "bg-berry-50 text-berry-700 ring-4 ring-berry-100",
};

function OrbIcon({ kind }: { kind: OrbKind }) {
  const size = 44;
  switch (kind) {
    case "connecting":
    case "working":
    case "saving":
      return <Loader2 size={size} className="animate-spin" strokeWidth={1.75} />;
    case "disclosure":
    case "agent":
    case "readback":
      return <Volume2 size={size} strokeWidth={1.75} />;
    case "blocked":
      return <MicOff size={size} strokeWidth={1.75} />;
    case "ready":
      return <ShieldCheck size={size} strokeWidth={1.75} />;
    default:
      return <Mic size={size} strokeWidth={1.75} />;
  }
}

/** The four safety steps every visit passes through, in order. */
function safetySteps(s: VoiceVisitState) {
  // A read-back is requested only once the required fields were heard; a correction clears it.
  const spoken = s.confirmVersion !== null;
  const readbackDone = spoken && s.playedReadbackVersion === s.confirmVersion;
  return [
    { label: "Disclosure", done: s.disclosurePlayed },
    { label: "Speak", done: spoken },
    { label: "Read-back", done: readbackDone },
    { label: "Confirm", done: s.phase === "saved" },
  ];
}

export function VoiceOrb({ state }: { state: VoiceVisitState }) {
  const view = orbView(state);
  const steps = safetySteps(state);
  const current = steps.findIndex((step) => !step.done);
  return (
    <div className="flex flex-col items-center gap-4 px-2 py-5 text-center">
      <div
        data-testid="voice-orb"
        data-orb={view.kind}
        className={`relative grid size-28 place-items-center rounded-full transition-colors duration-200 ${ORB_STYLE[view.kind]}`}
      >
        <OrbIcon kind={view.kind} />
      </div>
      <div role="status" aria-live="polite" className="flex flex-col items-center gap-1">
        <p className="text-xl leading-tight font-extrabold">
          <span lang="kn" className="block">
            {view.kn}
          </span>
          <span className="block text-base font-bold text-fg-2">{view.en}</span>
        </p>
        <p className="max-w-xs text-sm text-fg-2">{view.hint}</p>
      </div>
      <ol aria-label="Visit steps" className="grid w-full max-w-sm grid-cols-4 gap-1.5">
        {steps.map((step, i) => {
          const isCurrent = i === current;
          return (
            <li key={step.label} className="flex flex-col items-center gap-1.5" aria-current={isCurrent ? "step" : undefined}>
              <span
                className={`h-1.5 w-full rounded-full ${
                  step.done ? "bg-lime-600" : isCurrent ? "bg-berry-600" : "bg-neutral-200"
                }`}
              />
              <span
                className={`flex items-center gap-1 text-xs font-bold ${
                  step.done ? "text-lime-700" : isCurrent ? "text-berry-700" : "text-fg-3"
                }`}
              >
                {step.done && <Check size={12} aria-hidden="true" strokeWidth={3} />}
                {step.label}
                <span className="sr-only">{step.done ? " (done)" : isCurrent ? " (current)" : ""}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
