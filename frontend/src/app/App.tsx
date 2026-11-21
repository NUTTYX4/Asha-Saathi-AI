import { useEffect, useState } from "react";

import { DangerAlert } from "../features/alerts/components/DangerAlert";
import { FollowUpsPage } from "../features/followups/FollowUpsPage";
import { ConfirmBar } from "../features/visits/components/ConfirmBar";
import { RecordCard } from "../features/visits/components/RecordCard";
import { MicButton } from "../features/voice/components/MicButton";
import { StatusPill } from "../features/voice/components/StatusPill";
import { TranscriptPanel } from "../features/voice/components/TranscriptPanel";
import { useVoiceSession } from "../features/voice/hooks/useVoiceSession";

type Tab = "visit" | "followups";

export default function App() {
  const [tab, setTab] = useState<Tab>("visit");
  const [refreshKey, setRefreshKey] = useState(0);
  const { view, start, stop, confirm } = useVoiceSession();
  const active = view.connection === "open";

  useEffect(() => {
    if (view.lastSaved) setRefreshKey((k) => k + 1);
  }, [view.lastSaved]);

  return (
    <div className="mx-auto flex min-h-full max-w-md flex-col">
      <header className="flex items-center justify-between bg-ink px-4 pt-[max(env(safe-area-inset-top),0.75rem)] pb-3 text-white">
        <div>
          <h1 className="font-display text-2xl font-bold leading-none">ಆಶಾ ಸಾಥಿ</h1>
          <p className="text-xs opacity-75">ASHA SAATHI · ಧ್ವನಿ ಭೇಟಿ ದಾಖಲೆ</p>
        </div>
        <span className="whitespace-nowrap rounded-full bg-white/15 px-3 py-1 text-xs font-semibold" title="AI assistant">
          AI ಸಹಾಯಕ
        </span>
      </header>

      <nav className="grid grid-cols-2 border-b border-rule bg-sheet" aria-label="Sections">
        {(
          [
            ["visit", "ಭೇಟಿ · Visit"],
            ["followups", "ಮುಂದಿನ ಕೆಲಸ"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            aria-current={tab === key ? "page" : undefined}
            className={`min-h-12 font-display text-base font-medium ${tab === key ? "border-b-4 border-rose text-ink" : "text-ink-soft"}`}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="flex flex-1 flex-col gap-4 px-4 pt-4 pb-44">
        {tab === "visit" ? (
          <>
            <div className="flex items-center justify-between gap-2">
              <StatusPill state={view.sessionState} agentSpeaking={view.agentSpeaking} />
              {view.sttModel && <span className="text-xs text-ink-soft">STT {view.sttModel}</span>}
            </div>
            {view.error && (
              <p role="alert" className="rounded-xl bg-alarm-wash px-3 py-2 text-sm text-alarm">
                {view.error}
              </p>
            )}
            <DangerAlert alerts={view.alerts} />
            {view.lastSaved && (
              <p className="enter rounded-2xl bg-leaf px-4 py-3 font-semibold text-white">
                ✓ ಉಳಿಸಲಾಗಿದೆ · Saved visit #{view.lastSaved.visit_id} (ID {view.lastSaved.record.beneficiary_id})
              </p>
            )}
            {view.confirmVersion !== null && <ConfirmBar version={view.confirmVersion} onConfirm={confirm} />}
            {view.record && <RecordCard record={view.record} changedFields={view.changedFields} />}
            <TranscriptPanel lines={view.lines} />
          </>
        ) : (
          <FollowUpsPage refreshKey={refreshKey} />
        )}
      </main>

      {tab === "visit" && (
        <footer className="fixed inset-x-0 bottom-0 mx-auto max-w-md bg-gradient-to-t from-paper via-paper to-transparent px-4 pt-6 pb-[max(env(safe-area-inset-bottom),1rem)]">
          <MicButton
            active={active}
            connecting={view.connection === "connecting"}
            listening={view.sessionState === "listening" && !view.agentSpeaking}
            onStart={start}
            onStop={stop}
          />
        </footer>
      )}
    </div>
  );
}
