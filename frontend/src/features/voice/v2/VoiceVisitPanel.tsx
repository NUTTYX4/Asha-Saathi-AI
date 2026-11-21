import { CircleAlert, CircleCheck, Mic, RotateCcw, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { HouseholdDetail, PersonOut, VisitType } from "../../../types/contracts";
import { activeProgrammes } from "../../households/labels";
import { Badge, Button, Notice } from "../../ui/primitives";
import { useV2VoiceSession } from "../hooks/useV2VoiceSession";
import { V2DangerAlert } from "./V2DangerAlert";
import { VoiceOrb } from "./VoiceOrb";
import { Conversation, VisitRecordCard } from "./VoiceRecord";
import { canConfirm, confirmBlockReason, VISIT_TYPE_OPTIONS } from "./voiceVisit";

interface Props {
  household: HouseholdDetail;
  person: PersonOut;
  canRecord: boolean;
  onSessionLost: () => void;
  onVisitSaved?: () => void;
  onCheckHistory?: () => void;
  /** Reports whether a voice session is open (the workspace asks before leaving one). */
  onActiveChange?: (active: boolean) => void;
}

/**
 * Person-bound Gnani voice visit. All guards live in the session state (voiceVisit.ts):
 * the microphone opens only after the AI disclosure, and Confirm and Save is enabled only for the
 * latest version whose read-back has finished playing. Speaking "ಹೌದು" never saves.
 */
export function VoiceVisitPanel({
  household,
  person,
  canRecord,
  onSessionLost,
  onVisitSaved,
  onCheckHistory,
  onActiveChange,
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

  const live = state.phase === "connecting" || state.phase === "active" || state.phase === "saving";
  const panelRef = useRef<HTMLElement>(null);
  // When a visit starts, bring the panel (and its status orb) to the top of the screen.
  useEffect(() => {
    if (state.phase === "connecting") panelRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [state.phase]);
  useEffect(() => {
    onActiveChange?.(live);
  }, [live, onActiveChange]);
  useEffect(() => () => onActiveChange?.(false), [onActiveChange]);

  const programmes = activeProgrammes(person);
  const confirmReady = canConfirm(state);
  const blockReason = confirmBlockReason(state);
  const version = state.confirmVersion ?? state.record?.record_version ?? 1;

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
      ref={panelRef}
      aria-labelledby="voice-heading"
      data-testid="voice-panel"
      className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-4 shadow-sm"
    >
      <header className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="voice-heading" className="flex flex-col text-xl leading-tight font-extrabold">
            <span lang="kn">ಧ್ವನಿ ಭೇಟಿ</span>
            <span className="text-base text-fg-2">Voice visit</span>
          </h3>
          {state.bound && (
            <Badge tone="accent" icon={<ShieldCheck size={14} />} data-testid="bound-verified">
              Verified by server
            </Badge>
          )}
        </div>
        <p className="text-sm text-fg-2">
          For <strong className="text-fg">{person.full_name}</strong> ({person.public_id}) in household{" "}
          {household.public_id}. Nothing is saved until you press Confirm and Save.
        </p>
      </header>

      {!canRecord ? (
        <Notice tone="info" icon={<CircleAlert size={20} />} title="Read-only account">
          Only ASHA worker accounts record visits.
        </Notice>
      ) : (
        <>
          {state.phase === "idle" && (
            <div className="flex flex-col gap-4">
              <fieldset className="flex flex-col gap-2">
                <legend className="text-base font-bold">
                  <span lang="kn">ಭೇಟಿ ಪ್ರಕಾರ</span> Visit type
                </legend>
                <p className="text-sm text-fg-2">
                  Recorded programmes: {programmes.length > 0 ? programmes.join(", ") : "none"}. Choose the type
                  yourself.
                </p>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  {VISIT_TYPE_OPTIONS.map((opt) => {
                    const checked = selectedVisitType === opt.value;
                    return (
                      <label
                        key={opt.value}
                        className={`relative flex min-h-16 cursor-pointer flex-col justify-center rounded-md border px-3 py-2 transition-colors duration-150 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-berry-600 ${
                          checked
                            ? "border-2 border-berry-600 bg-berry-50"
                            : "border-control bg-surface hover:border-neutral-700"
                        }`}
                      >
                        <input
                          type="radio"
                          name={`visit-type-${person.id}`}
                          value={opt.value}
                          checked={checked}
                          onChange={() => setSelectedVisitType(opt.value)}
                          className="absolute inset-0 m-0 cursor-pointer appearance-none rounded-md opacity-0"
                        />
                        <span lang="kn" className="text-base font-bold leading-snug">
                          {opt.kn}
                        </span>
                        <span className="text-sm font-semibold text-fg-2">{opt.en}</span>
                        {checked && (
                          <CircleCheck
                            size={18}
                            aria-hidden="true"
                            className="absolute top-2 right-2 text-berry-600"
                          />
                        )}
                      </label>
                    );
                  })}
                </div>
              </fieldset>
              <Button block icon={<Mic size={20} />} onClick={handleStart} disabled={!selectedVisitType}>
                Start voice visit
              </Button>
              <p className="text-center text-xs text-fg-3">
                Speech goes to Gnani on the server. Audio and transcripts are not stored.
              </p>
            </div>
          )}

          {state.phase === "connecting" && (
            <div className="flex flex-col gap-2">
              <VoiceOrb state={state} />
              <Button variant="ghost" icon={<X size={20} />} onClick={cancel}>
                Cancel visit
              </Button>
            </div>
          )}

          {(state.phase === "active" || state.phase === "saving") && (
            <div className="flex flex-col gap-4">
              <V2DangerAlert alerts={state.alerts} />
              <VoiceOrb state={state} />
              {state.sttModel && (
                <p className="-mt-3 text-center text-xs text-fg-3">Speech model: {state.sttModel}</p>
              )}

              {state.clarification && (
                <Notice tone="brand" icon={<CircleAlert size={20} />} title="ASHA Saathi asks" role="status">
                  <span className="text-base">{state.clarification}</span>
                </Notice>
              )}

              {state.record && <VisitRecordCard record={state.record} changedFields={state.changedFields} />}
              <Conversation lines={state.lines} />

              {/* Confirmation dock: stays in thumb reach while the record scrolls. */}
              <div className="sticky bottom-0 z-10 -mx-4 -mb-4 flex flex-col gap-2 rounded-b-xl border-t border-line bg-surface px-4 pt-3 pb-[max(env(safe-area-inset-bottom),0.75rem)] shadow-[0_-8px_16px_rgba(31,26,24,0.06)]">
                <Button
                  block
                  data-testid="confirm-save"
                  onClick={confirm}
                  disabled={!confirmReady || state.phase === "saving"}
                  icon={<CircleCheck size={20} />}
                >
                  {state.phase === "saving" ? "Saving…" : `Confirm and Save (version ${version})`}
                </Button>
                {blockReason && state.phase === "active" && (
                  <p className="text-center text-xs font-semibold text-fg-2">{blockReason}</p>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="md"
                    icon={<RotateCcw size={18} />}
                    aria-label="Replay read-back"
                    onClick={replayReadback}
                    disabled={state.phase === "saving" || !(state.readbackAudioFailed || state.confirmVersion !== null)}
                  >
                    Replay
                  </Button>
                  <Button variant="ghost" size="md" icon={<X size={18} />} onClick={cancel} disabled={state.phase === "saving"}>
                    Cancel visit
                  </Button>
                </div>
              </div>
            </div>
          )}

          {state.phase === "saved" && state.saved && (
            <div
              data-testid="visit-saved"
              className="v2-rise flex flex-col gap-3 rounded-lg border border-lime-500 bg-lime-100 p-4 text-on-accent"
            >
              <div className="flex items-start gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-lime-300">
                  <CircleCheck size={24} aria-hidden="true" />
                </span>
                <div>
                  <p className="text-lg font-extrabold leading-tight">
                    <span lang="kn">ಉಳಿಸಲಾಗಿದೆ</span> Visit saved
                  </p>
                  <p className="text-sm">
                    Saved for {person.full_name} ({person.public_id}).{" "}
                    {state.saved.idempotent_replay ? "It was already saved; this is the same visit." : ""}
                  </p>
                </div>
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                <dt className="font-semibold">Version</dt>
                <dd>{state.saved.record_version}</dd>
                <dt className="font-semibold">Saved at</dt>
                <dd>
                  {new Date(state.saved.confirmed_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                </dd>
                <dt className="font-semibold">Visit ID</dt>
                <dd>{state.saved.visit_id.slice(0, 8)}</dd>
              </dl>
              <Button variant="outline" onClick={handleReset} className="bg-surface">
                Start another visit
              </Button>
            </div>
          )}

          {state.phase === "ended" && (
            <Notice tone="info" icon={<CircleAlert size={20} />} title="Visit ended">
              <p>{state.notice ?? "Session ended. Nothing was saved."}</p>
              <Button variant="outline" size="md" className="mt-2" onClick={handleReset}>
                Start again
              </Button>
            </Notice>
          )}

          {state.phase === "save_unknown" && (
            <Notice tone="warning" icon={<CircleAlert size={20} />} title="Save status unknown" role="alert">
              <p>{state.notice ?? "Save status unknown. Check this person's visit history before recording again."}</p>
              <Button variant="outline" size="md" className="mt-2" onClick={() => onCheckHistory?.()}>
                Check history
              </Button>
            </Notice>
          )}

          {state.error && (
            <Notice tone="error" icon={<CircleAlert size={20} />} role="status">
              {state.error}
            </Notice>
          )}
        </>
      )}
    </section>
  );
}
