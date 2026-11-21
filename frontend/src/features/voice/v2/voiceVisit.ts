import { VISIT_LABEL } from "../../../lib/labels";
import type { ServerEvent } from "../../../lib/api";
import type {
  AlertRaised,
  SessionState,
  V2SessionBound,
  V2VisitOut,
  VisitRecord,
  VisitType,
} from "../../../types/contracts";
import type { TranscriptLine } from "../hooks/useVoiceSession";

export type VoicePhase =
  | "idle"
  | "connecting"
  | "active"
  | "saving"
  | "saved"
  | "ended"
  | "save_unknown";

export interface SavedSummary {
  visit_id: string;
  record_version: number;
  confirmed_at: string;
  idempotent_replay: boolean;
}

export interface VoiceVisitState {
  phase: VoicePhase;
  clientVisitId: string | null;
  sessionState: SessionState;
  sttModel: string | null;
  bound: V2SessionBound | null;
  record: VisitRecord | null;
  changedFields: string[];
  lines: TranscriptLine[];
  nextLineId: number;
  alerts: AlertRaised[];
  clarification: string | null;
  confirmVersion: number | null;
  playedReadbackVersion: number | null;
  readbackAudioFailed: boolean;
  disclosurePlayed: boolean;
  disclosureFailed: boolean;
  speechInProgress: boolean;
  agentSpeaking: boolean;
  saved: SavedSummary | null;
  notice: string | null;
  error: string | null;
}

export type VoiceVisitAction =
  | { type: "start"; clientVisitId: string }
  | { type: "server"; event: ServerEvent }
  | { type: "clip_ended"; purpose: string; recordVersion: number | null }
  | { type: "clip_failed"; purpose: string }
  | { type: "speaking"; speaking: boolean }
  | { type: "confirm_sent" }
  | { type: "local_end"; notice: string }
  | { type: "connection_lost" }
  | { type: "receipt_found"; visit: V2VisitOut }
  | { type: "receipt_missing" }
  | { type: "receipt_unknown" }
  | { type: "reset" };

export const initialVoiceVisitState: VoiceVisitState = {
  phase: "idle",
  clientVisitId: null,
  sessionState: "idle",
  sttModel: null,
  bound: null,
  record: null,
  changedFields: [],
  lines: [],
  nextLineId: 1,
  alerts: [],
  clarification: null,
  confirmVersion: null,
  playedReadbackVersion: null,
  readbackAudioFailed: false,
  disclosurePlayed: false,
  disclosureFailed: false,
  speechInProgress: false,
  agentSpeaking: false,
  saved: null,
  notice: null,
  error: null,
};

export const VISIT_TYPE_OPTIONS: { value: VisitType; kn: string; en: string }[] = [
  { value: "ANC", kn: VISIT_LABEL.ANC.kn, en: VISIT_LABEL.ANC.en },
  { value: "PNC", kn: VISIT_LABEL.PNC.kn, en: VISIT_LABEL.PNC.en },
  { value: "newborn", kn: VISIT_LABEL.newborn.kn, en: VISIT_LABEL.newborn.en },
  { value: "immunisation", kn: VISIT_LABEL.immunisation.kn, en: VISIT_LABEL.immunisation.en },
  { value: "routine", kn: VISIT_LABEL.routine.kn, en: VISIT_LABEL.routine.en },
  { value: "unknown", kn: "ತಿಳಿದಿಲ್ಲ", en: "Not sure" },
];

const MAX_LINES = 30;

function appendLine(
  state: VoiceVisitState,
  who: TranscriptLine["who"],
  text: string,
): Pick<VoiceVisitState, "lines" | "nextLineId"> {
  const next = [...state.lines, { id: state.nextLineId, who, text }];
  return {
    lines: next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next,
    nextLineId: state.nextLineId + 1,
  };
}

function handleServerEvent(state: VoiceVisitState, event: ServerEvent): VoiceVisitState {
  switch (event.type) {
    case "session.started":
      return {
        ...state,
        phase: "active",
        sttModel: event.stt_model ?? null,
      };
    case "v2.session.bound":
      return { ...state, bound: event };
    case "state.changed": {
      const settled =
        event.state === "awaiting_confirmation" ||
        event.state === "listening" ||
        event.state === "saved" ||
        event.state === "idle";
      return {
        ...state,
        sessionState: event.state,
        speechInProgress: settled ? false : state.speechInProgress,
      };
    }
    case "speech.started":
      return { ...state, speechInProgress: true };
    case "transcript.final":
      return { ...state, speechInProgress: true, ...appendLine(state, "worker", event.text) };
    case "agent.audio": {
      const linePatch = appendLine(state, "agent", event.text);
      const missingAudio = !event.audio_b64;
      const readbackAudioFailed =
        event.purpose === "readback" ? missingAudio : state.readbackAudioFailed;
      const disclosureFailed =
        event.purpose === "disclosure" ? missingAudio : state.disclosureFailed;
      return {
        ...state,
        ...linePatch,
        readbackAudioFailed,
        disclosureFailed,
      };
    }
    case "agent.audio.cancel":
      return state;
    case "record.updated": {
      const stale = state.confirmVersion !== null && event.record.record_version !== state.confirmVersion;
      return {
        ...state,
        record: event.record,
        changedFields: event.changed_fields,
        clarification: null,
        confirmVersion: stale ? null : state.confirmVersion,
        playedReadbackVersion: stale ? null : state.playedReadbackVersion,
        readbackAudioFailed: stale ? false : state.readbackAudioFailed,
      };
    }
    case "record.confirmation_requested":
      return {
        ...state,
        confirmVersion: event.record_version,
        playedReadbackVersion: null,
        readbackAudioFailed: false,
        speechInProgress: false,
      };
    case "alert.raised":
      return { ...state, alerts: [...state.alerts, event] };
    case "clarification.requested":
      return { ...state, clarification: event.prompt };
    case "session.error":
      return {
        ...state,
        error: event.message,
        phase: state.phase === "saving" ? "active" : state.phase,
      };
    case "v2.visit.saved":
      return {
        ...state,
        phase: "saved",
        speechInProgress: false,
        saved: {
          visit_id: event.visit_id,
          record_version: event.record_version,
          confirmed_at: event.confirmed_at,
          idempotent_replay: event.idempotent_replay,
        },
        error: null,
      };
    case "session.ended":
      if (state.phase === "saved") return state;
      return {
        ...state,
        phase: "ended",
        notice: event.message,
        speechInProgress: false,
        agentSpeaking: false,
      };
    case "record.saved":
      return state;
  }
}

export function voiceVisitReducer(state: VoiceVisitState, action: VoiceVisitAction): VoiceVisitState {
  switch (action.type) {
    case "start":
      return {
        ...initialVoiceVisitState,
        phase: "connecting",
        clientVisitId: action.clientVisitId,
      };
    case "server":
      return handleServerEvent(state, action.event);
    case "clip_ended":
      if (action.purpose === "disclosure") {
        return { ...state, disclosurePlayed: true, disclosureFailed: false };
      }
      if (
        action.purpose === "readback" &&
        action.recordVersion !== null &&
        action.recordVersion === state.confirmVersion
      ) {
        return {
          ...state,
          playedReadbackVersion: action.recordVersion,
          readbackAudioFailed: false,
        };
      }
      return state;
    case "clip_failed":
      if (action.purpose === "readback") {
        return { ...state, readbackAudioFailed: true };
      }
      if (action.purpose === "disclosure") {
        return { ...state, disclosureFailed: true };
      }
      return state;
    case "speaking":
      return { ...state, agentSpeaking: action.speaking };
    case "confirm_sent":
      return { ...state, phase: "saving", error: null };
    case "local_end":
      if (state.phase === "saved") return state;
      return {
        ...state,
        phase: "ended",
        notice: action.notice,
        agentSpeaking: false,
      };
    case "connection_lost":
      if (state.phase === "saving") {
        return {
          ...state,
          phase: "save_unknown",
          notice: "Checking whether the visit was saved…",
          agentSpeaking: false,
        };
      }
      if (state.phase === "active" || state.phase === "connecting") {
        return {
          ...state,
          phase: "ended",
          notice: "Connection lost. Nothing was saved.",
          agentSpeaking: false,
        };
      }
      return state;
    case "receipt_found":
      return {
        ...state,
        phase: "saved",
        saved: {
          visit_id: action.visit.id,
          record_version: action.visit.record_version,
          confirmed_at: action.visit.confirmed_at,
          idempotent_replay: false,
        },
        notice: null,
        error: null,
      };
    case "receipt_missing":
      return {
        ...state,
        phase: "ended",
        notice: "The connection dropped before the save completed. Nothing was saved.",
        agentSpeaking: false,
      };
    case "receipt_unknown":
      return {
        ...state,
        phase: "save_unknown",
        notice: "Save status unknown. Check this person's visit history before recording again.",
        agentSpeaking: false,
      };
    case "reset":
      return initialVoiceVisitState;
  }
}

/** True only when the latest record has completed read-back and has no missing required fields. */
export function canConfirm(s: VoiceVisitState): boolean {
  return (
    s.phase === "active" &&
    !s.speechInProgress &&
    s.confirmVersion !== null &&
    s.record !== null &&
    s.record.record_version === s.confirmVersion &&
    s.playedReadbackVersion === s.confirmVersion &&
    s.record.missing_fields.length === 0
  );
}

/** Short bilingual reason why Confirm and Save is currently disabled, or null when ready. */
export function confirmBlockReason(s: VoiceVisitState): string | null {
  if (canConfirm(s)) return null;
  if (s.phase !== "active") return null;
  if (s.speechInProgress) {
    return "ಮಾತು ಪರಿಶೀಲಿಸುತ್ತಿದ್ದೇನೆ · Processing spoken update…";
  }
  if (s.readbackAudioFailed) {
    return "ಓದು ಕೇಳಿಸಲಿಲ್ಲ · Read-back audio failed — tap Replay read-back.";
  }
  if (s.record && s.record.missing_fields.length > 0) {
    return "ಬಾಕಿ ಮಾಹಿತಿ ಬೇಕು · Complete missing fields before saving.";
  }
  if (s.confirmVersion === null || s.playedReadbackVersion !== s.confirmVersion) {
    return "ಓದುವಿಕೆ ಮುಗಿಯಲಿ · Waiting for read-back to finish.";
  }
  return null;
}

export function boundMatches(
  bound: V2SessionBound | null,
  householdPublicId: string,
  personPublicId: string,
): boolean {
  return (
    bound !== null &&
    bound.household_public_id === householdPublicId &&
    bound.person_public_id === personPublicId
  );
}
