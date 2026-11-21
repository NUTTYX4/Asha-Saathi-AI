import { useEffect, useRef, useState } from "react";

import type { HouseholdDetail, PersonOut, VisitType } from "../../../types/contracts";
import { activeProgrammes } from "../../households/labels";
import { RecordCard } from "../../visits/components/RecordCard";
import { StatusPill } from "../components/StatusPill";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { useV2VoiceSession } from "../hooks/useV2VoiceSession";
import { V2DangerAlert } from "./V2DangerAlert";
import { canConfirm, confirmBlockReason, VISIT_TYPE_OPTIONS } from "./voiceVisit";

interface Props {
  household: HouseholdDetail;
  person: PersonOut;
  canRecord: boolean;
  onSessionLost: () => void;
  onVisitSaved?: () => void;
  onCheckHistory?: () => void;
}

const button = "min-h-12 rounded-xl px-4 font-semibold disabled:opacity-50";

export function VoiceVisitPanel({
  household,
  person,
  canRecord,
  onSessionLost,
  onVisitSaved,
  onCheckHistory,
}: Props) {
  const { state, start, confirm, replayReadback, cancel, reset } = useV2VoiceSession(onSessionLost);
  const [selectedVisitType, setSelectedVisitType] = useState<VisitType | null>(null);
  const lastSavedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (state.phase === "saved" && state.saved && state.saved.visit_id !== lastSavedIdRef.current) {
      lastSavedIdRef.current = state.saved.visit_id;
      onVisitSaved?.();
    }
  }, [onVisitSaved, state.phase, state.saved]);

  const programmes = activeProgrammes(person);
  const confirmReady = canConfirm(state);
  const blockReason = confirmBlockReason(state);

  function handleStart() {
    if (!selectedVisitType) return;
    start({
      householdId: household.id,
      personId: person.id,
      householdPublicId: household.public_id,
      personPublicId: person.public_id,
      visitType: selectedVisitType,
    });
  }

  function handleReset() {
    setSelectedVisitType(null);
    reset();
  }

  return (
    <section
      aria-label="Member voice visit"
      data-testid="voice-panel"
      className="mt-3 flex flex-col gap-3 rounded-xl border border-rule bg-paper p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <p className="font-semibold text-ink break-words">
          Voice visit for {person.full_name} ({person.public_id}) · Household {household.public_id}
        </p>
        {state.bound && (
          <span
            data-testid="bound-verified"
            className="rounded-full bg-leaf/15 px-2 py-0.5 font-semibold text-leaf"
          >
            verified by server
          </span>
        )}
      </div>

      {!canRecord ? (
        <p className="rounded-xl bg-sheet px-3 py-2 text-sm text-ink-soft">
          Only ASHA worker accounts record visits.
        </p>
      ) : (
        <>
          {state.phase === "idle" && (
            <div className="flex flex-col gap-3">
              <fieldset className="flex flex-col gap-1.5">
                <legend className="text-sm font-semibold text-ink">Visit type (required)</legend>
                <p className="text-xs text-ink-soft">
                  Recorded programmes: {programmes.length > 0 ? programmes.join(", ") : "None"} (choose the type yourself)
                </p>
                <div className="mt-1 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                  {VISIT_TYPE_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      className={`flex min-h-11 cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2 text-sm ${
                        selectedVisitType === opt.value
                          ? "border-ink bg-sheet font-semibold"
                          : "border-rule bg-sheet/70"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`visit-type-${person.id}`}
                        value={opt.value}
                        checked={selectedVisitType === opt.value}
                        onChange={() => setSelectedVisitType(opt.value)}
                        className="h-4 w-4 accent-rose"
                      />
                      <span>
                        {opt.kn} · <span className="text-ink-soft">{opt.en}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <button
                type="button"
                onClick={handleStart}
                disabled={!selectedVisitType}
                className={`${button} w-full bg-rose text-white`}
              >
                Start voice visit
              </button>
              <p className="text-xs text-ink-soft">
                Uses Gnani speech. Nothing is saved until you press Confirm and Save.
              </p>
            </div>
          )}

          {state.phase === "connecting" && (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-ink-soft">Connecting voice session…</p>
              <button type="button" onClick={cancel} className={`${button} border border-ink bg-sheet`}>
                Cancel visit
              </button>
            </div>
          )}

          {(state.phase === "active" || state.phase === "saving") && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <StatusPill state={state.sessionState} agentSpeaking={state.agentSpeaking} />
                {state.sttModel && <span className="text-xs text-ink-soft">STT {state.sttModel}</span>}
              </div>

              {state.disclosureFailed ? (
                <p role="alert" className="rounded-xl bg-alarm-wash px-3 py-2 text-sm text-alarm">
                  Disclosure audio failed; the microphone stays off. Cancel and try again.
                </p>
              ) : (
                <p className="rounded-xl bg-sheet px-3 py-2 text-xs font-medium text-ink-soft">
                  {state.disclosurePlayed
                    ? "Microphone on"
                    : "Waiting for the AI disclosure to finish"}
                </p>
              )}

              <V2DangerAlert alerts={state.alerts} />

              {state.clarification && (
                <div role="status" className="rounded-xl border border-rose/40 bg-sheet px-3 py-2 text-sm">
                  <p className="font-semibold text-rose">Clarification needed</p>
                  <p className="mt-0.5 text-ink">{state.clarification}</p>
                </div>
              )}

              {state.record && <RecordCard record={state.record} changedFields={state.changedFields} />}

              <TranscriptPanel lines={state.lines} />

              <div className="flex flex-col gap-2 rounded-2xl border-2 border-leaf/60 bg-sheet p-3">
                <p className="text-xs leading-snug text-ink-soft">
                  Check the read-back. Speak to correct a field. Saying &lsquo;ಹೌದು&rsquo; does not save; press the button.
                </p>
                <button
                  type="button"
                  data-testid="confirm-save"
                  onClick={confirm}
                  disabled={!confirmReady || state.phase === "saving"}
                  className={`${button} w-full bg-leaf text-white`}
                >
                  {state.phase === "saving"
                    ? "Saving…"
                    : `Confirm and Save (version ${state.confirmVersion ?? state.record?.record_version ?? 1})`}
                </button>
                {blockReason && state.phase === "active" && (
                  <p className="text-xs text-ink-soft">{blockReason}</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {(state.readbackAudioFailed || state.confirmVersion !== null) && (
                    <button
                      type="button"
                      onClick={replayReadback}
                      disabled={state.phase === "saving"}
                      className={`${button} flex-1 border border-ink bg-paper text-sm`}
                    >
                      Replay read-back
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={cancel}
                    disabled={state.phase === "saving"}
                    className={`${button} flex-1 border border-ink bg-paper text-sm`}
                  >
                    Cancel visit
                  </button>
                </div>
              </div>
            </div>
          )}

          {state.phase === "saved" && state.saved && (
            <div data-testid="visit-saved" className="flex flex-col gap-2 rounded-xl bg-leaf px-3.5 py-3 text-white">
              <p className="text-sm font-semibold">
                Saved ✓ · version {state.saved.record_version} ·{" "}
                {new Date(state.saved.confirmed_at).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}{" "}
                · visit id {state.saved.visit_id.slice(0, 8)}
              </p>
              {state.saved.idempotent_replay && (
                <p className="text-xs opacity-90">Already saved earlier — showing the same visit receipt.</p>
              )}
              <button
                type="button"
                onClick={handleReset}
                className={`${button} mt-1 bg-sheet text-sm text-ink`}
              >
                Start another visit
              </button>
            </div>
          )}

          {state.phase === "ended" && (
            <div className="flex flex-col gap-2 rounded-xl border border-rule bg-sheet px-3 py-2.5 text-sm">
              <p>{state.notice ?? "Session ended. Nothing was saved."}</p>
              <button
                type="button"
                onClick={handleReset}
                className={`${button} border border-ink bg-paper text-sm`}
              >
                Start again
              </button>
            </div>
          )}

          {state.phase === "save_unknown" && (
            <div role="alert" className="flex flex-col gap-2 rounded-xl bg-alarm-wash px-3 py-2.5 text-sm text-alarm">
              <p>{state.notice ?? "Save status unknown. Check this person's visit history before recording again."}</p>
              <button
                type="button"
                onClick={() => onCheckHistory?.()}
                className={`${button} border border-alarm bg-sheet text-sm text-alarm`}
              >
                Check history
              </button>
            </div>
          )}

          {state.error && (
            <p role="status" className="rounded-xl bg-alarm-wash px-3 py-2 text-xs font-medium text-alarm">
              {state.error}
            </p>
          )}
        </>
      )}
    </section>
  );
}
