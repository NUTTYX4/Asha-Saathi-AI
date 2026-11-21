/* AUTO-GENERATED from backend Pydantic schemas (contracts/contracts.schema.json). Do not edit; run npm run gen:types. */

export type VisitType = "ANC" | "PNC" | "newborn" | "immunisation" | "routine" | "unknown";
export type RecordStatus = "draft" | "pending_confirmation" | "confirmed";
export type VisitType1 = "ANC" | "PNC" | "newborn" | "immunisation" | "routine" | "unknown";
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
export type VisitType2 = "ANC" | "PNC" | "newborn" | "immunisation" | "routine" | "unknown";

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
    | SessionError
    | V2SessionBound
    | V2VisitSaved
    | SessionEnded;
  client_event: SessionStart | RecordConfirm | SessionStop;
  v2_login_request: LoginRequest;
  v2_me: MeOut;
  v2_territory: TerritoryOut;
  v2_household_pin: HouseholdPin;
  v2_nearby_household: NearbyHousehold;
  v2_household_detail: HouseholdDetail;
  v2_person: PersonOut;
  v2_client_event: V2SessionStart | RecordConfirm | SessionStop | PlaybackCompleted | ReadbackRequest | SessionCancel;
  v2_visit: V2VisitOut;
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
  scope: "this_visit" | "other_person";
  rule_status: string;
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
  record_version: number | null;
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
/**
 * V2: the server-verified, immutable subject of this voice session (display fields only).
 */
export interface V2SessionBound {
  seq: number;
  turn_id: number;
  type: "v2.session.bound";
  household_public_id: string;
  person_public_id: string;
  person_display_name: string;
  visit_type: VisitType1;
  client_visit_id: string;
  [k: string]: unknown;
}
/**
 * V2: the one confirmed visit for this logical visit key (repeat confirms replay it).
 */
export interface V2VisitSaved {
  seq: number;
  turn_id: number;
  type: "v2.visit.saved";
  visit_id: string;
  person_public_id: string;
  record_version: number;
  confirmed_at: string;
  idempotent_replay: boolean;
  [k: string]: unknown;
}
/**
 * V2: the session stopped without saving (revoked, superseded, expired or cancelled).
 */
export interface SessionEnded {
  seq: number;
  turn_id: number;
  type: "session.ended";
  reason: "revoked" | "superseded" | "expired" | "idle" | "cancelled" | "provider_unavailable";
  message: string;
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
export interface LoginRequest {
  username: string;
  password: string;
  [k: string]: unknown;
}
export interface MeOut {
  user_id: string;
  username: string;
  display_name: string;
  role: "worker" | "supervisor" | "admin";
  territories: TerritoryOut[];
  [k: string]: unknown;
}
export interface TerritoryOut {
  id: string;
  code: string;
  name: string;
  active: boolean;
  is_demo_data: boolean;
  [k: string]: unknown;
}
/**
 * Map-safe summary: location and counts only (no programmes, no conditions).
 */
export interface HouseholdPin {
  id: string;
  public_id: string;
  label: string;
  landmark: string | null;
  territory_code: string;
  latitude: number;
  longitude: number;
  location_source: string;
  member_count: number;
  is_demo_data: boolean;
  [k: string]: unknown;
}
/**
 * A map pin plus its server-computed distance from the query point (metres, geography).
 * A suggestion only: being near a pin never selects or confirms that household.
 */
export interface NearbyHousehold {
  id: string;
  public_id: string;
  label: string;
  landmark: string | null;
  territory_code: string;
  latitude: number;
  longitude: number;
  location_source: string;
  member_count: number;
  is_demo_data: boolean;
  distance_m: number;
  [k: string]: unknown;
}
export interface HouseholdDetail {
  id: string;
  public_id: string;
  label: string;
  landmark: string | null;
  territory_code: string;
  latitude: number;
  longitude: number;
  location_source: string;
  member_count: number;
  is_demo_data: boolean;
  latest_survey: SurveyOut | null;
  [k: string]: unknown;
}
export interface SurveyOut {
  survey_version: string;
  status: string;
  drinking_water_source: string;
  has_toilet: boolean | null;
  submitted_on: string;
  [k: string]: unknown;
}
export interface PersonOut {
  id: string;
  public_id: string;
  household_public_id: string;
  full_name: string;
  sex: "female" | "male" | "other" | "not_recorded";
  date_of_birth: string | null;
  age: AgeOut;
  relationship_to_head:
    | "head"
    | "spouse"
    | "son"
    | "daughter"
    | "father"
    | "mother"
    | "father_in_law"
    | "mother_in_law"
    | "son_in_law"
    | "daughter_in_law"
    | "grandson"
    | "granddaughter"
    | "brother"
    | "sister"
    | "other";
  residence_status: string;
  programmes: EnrolmentOut[];
  relationships: RelationshipOut[];
  is_demo_data: boolean;
  [k: string]: unknown;
}
export interface AgeOut {
  basis: "date_of_birth" | "recorded_age" | "unknown";
  years?: number | null;
  months?: number | null;
  days?: number | null;
  [k: string]: unknown;
}
export interface EnrolmentOut {
  programme: string;
  status: string;
  started_on: string;
  source: string;
  [k: string]: unknown;
}
export interface RelationshipOut {
  relationship_type: string;
  direction: "outgoing" | "incoming";
  other_person_public_id: string;
  other_person_name: string;
  [k: string]: unknown;
}
/**
 * First frame of a V2 voice visit. IDs come from the explicit Phase 4 selection and are
 * re-authorised by the server; visit_type is the worker's explicit choice (may be unknown).
 */
export interface V2SessionStart {
  type: "v2.session.start";
  household_id: string;
  person_id: string;
  client_visit_id: string;
  visit_type: VisitType2;
  [k: string]: unknown;
}
/**
 * The browser finished playing an agent clip. For a read-back it names the version read.
 */
export interface PlaybackCompleted {
  type: "playback.completed";
  purpose: "disclosure" | "readback";
  record_version: number | null;
  [k: string]: unknown;
}
/**
 * Ask for the read-back of the current version again (e.g. after a TTS failure).
 */
export interface ReadbackRequest {
  type: "readback.request";
  [k: string]: unknown;
}
export interface SessionCancel {
  type: "session.cancel";
  [k: string]: unknown;
}
export interface V2VisitOut {
  id: string;
  client_visit_id: string;
  person_public_id: string;
  household_public_id: string;
  recorded_by: string;
  visit_type: VisitType1;
  subject_population: string;
  weight_kg: number | null;
  vaccinations_due: string[] | null;
  next_visit_date: string | null;
  danger_signs: string[];
  requires_phc_referral: boolean;
  rule_status: string;
  ruleset_version: string;
  extraction_source: string;
  record_version: number;
  confirmed_at: string;
  is_demo_data: boolean;
  [k: string]: unknown;
}
