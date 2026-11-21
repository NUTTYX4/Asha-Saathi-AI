/* AUTO-GENERATED from backend Pydantic schemas (contracts/contracts.schema.json). Do not edit; run npm run gen:types. */

export type VisitType = "ANC" | "PNC" | "newborn" | "immunisation" | "unknown";
export type RecordStatus = "draft" | "pending_confirmation" | "confirmed";
export type VisitType1 = "ANC" | "PNC" | "newborn" | "immunisation" | "unknown";
export type SessionState =
  | "idle"
  | "listening"
  | "transcribing"
  | "processing"
  | "clarifying"
  | "reading_back"
  | "awaiting_confirmation"
  | "confirmed"
  | "saved"
  | "error";

/**
 * Root container so one schema file holds every shared type.
 */
export interface AshaSaathiContracts {
  visit_record: VisitRecord;
  saved_visit: SavedVisit;
  follow_up_item: FollowUpItem;
  server_event:
    | SessionStarted
    | StateChanged
    | SpeechStarted
    | TranscriptFinal
    | RecordUpdated
    | ClarificationRequested
    | AlertRaised
    | AgentSpeech
    | AgentAudioCancel
    | ConfirmationRequested
    | RecordSaved
    | SessionError;
  client_event: SessionStart | RecordConfirm | SessionStop;
  [k: string]: unknown;
}
/**
 * The in-progress or confirmed visit record shared by backend and frontend.
 */
export interface VisitRecord {
  beneficiary_id: string | null;
  visit_type: VisitType;
  weight_kg: number | null;
  vaccinations_due: string[] | null;
  next_visit_date: string | null;
  /**
   * Matched safety rule IDs
   */
  danger_signs: string[];
  requires_phc_referral: boolean;
  language: string | null;
  status: RecordStatus;
  record_version: number;
  missing_fields: string[];
  [k: string]: unknown;
}
/**
 * A confirmed visit as persisted. No transcripts or audio are stored.
 */
export interface SavedVisit {
  id: number;
  beneficiary_id: string;
  visit_type: VisitType1;
  weight_kg: number | null;
  vaccinations_due: string[] | null;
  next_visit_date: string | null;
  danger_signs: string[];
  requires_phc_referral: boolean;
  language: string | null;
  record_version: number;
  created_at: string;
  [k: string]: unknown;
}
export interface FollowUpItem {
  visit_id: number;
  beneficiary_id: string;
  visit_type: VisitType1;
  due_date: string | null;
  vaccinations_due: string[] | null;
  requires_phc_referral: boolean;
  danger_signs: string[];
  [k: string]: unknown;
}
export interface SessionStarted {
  seq: number;
  turn_id: number;
  type: "session.started";
  session_id: string;
  stt_model: string | null;
  [k: string]: unknown;
}
export interface StateChanged {
  seq: number;
  turn_id: number;
  type: "state.changed";
  state: SessionState;
  [k: string]: unknown;
}
export interface SpeechStarted {
  seq: number;
  turn_id: number;
  type: "speech.started";
  [k: string]: unknown;
}
export interface TranscriptFinal {
  seq: number;
  turn_id: number;
  type: "transcript.final";
  text: string;
  language: string | null;
  [k: string]: unknown;
}
export interface RecordUpdated {
  seq: number;
  turn_id: number;
  type: "record.updated";
  record: VisitRecord;
  changed_fields: string[];
  [k: string]: unknown;
}
export interface ClarificationRequested {
  seq: number;
  turn_id: number;
  type: "clarification.requested";
  field: string;
  prompt: string;
  [k: string]: unknown;
}
export interface AlertRaised {
  seq: number;
  turn_id: number;
  type: "alert.raised";
  rule_ids: string[];
  labels: string[];
  message: string;
  [k: string]: unknown;
}
/**
 * Agent utterance: text plus base64 WAV from Timbre (audio absent if TTS failed).
 */
export interface AgentSpeech {
  seq: number;
  turn_id: number;
  type: "agent.audio";
  purpose: "disclosure" | "clarification" | "readback" | "alert" | "saved" | "info";
  text: string;
  audio_b64: string | null;
  mime_type: string;
  [k: string]: unknown;
}
export interface AgentAudioCancel {
  seq: number;
  turn_id: number;
  type: "agent.audio.cancel";
  [k: string]: unknown;
}
export interface ConfirmationRequested {
  seq: number;
  turn_id: number;
  type: "record.confirmation_requested";
  record_version: number;
  [k: string]: unknown;
}
export interface RecordSaved {
  seq: number;
  turn_id: number;
  type: "record.saved";
  visit_id: number;
  record: VisitRecord;
  [k: string]: unknown;
}
export interface SessionError {
  seq: number;
  turn_id: number;
  type: "session.error";
  code: string;
  message: string;
  retryable: boolean;
  [k: string]: unknown;
}
export interface SessionStart {
  type: "session.start";
  [k: string]: unknown;
}
/**
 * Tap fallback for confirmation; must name the version that was read back.
 */
export interface RecordConfirm {
  type: "record.confirm";
  record_version: number;
  [k: string]: unknown;
}
export interface SessionStop {
  type: "session.stop";
  [k: string]: unknown;
}
