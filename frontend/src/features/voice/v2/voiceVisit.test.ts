import { describe, expect, it } from "vitest";

import type { V2SessionBound, V2VisitOut, VisitRecord } from "../../../types/contracts";
import {
  boundMatches,
  canConfirm,
  confirmBlockReason,
  initialVoiceVisitState,
  VISIT_TYPE_OPTIONS,
  voiceVisitReducer,
  type VoiceVisitState,
} from "./voiceVisit";

function makeRecord(overrides: Partial<VisitRecord> = {}): VisitRecord {
  return {
    beneficiary_id: "P-012",
    visit_type: "newborn",
    weight_kg: 2.5,
    vaccinations_due: null,
    next_visit_date: "2026-11-28",
    danger_signs: [],
    requires_phc_referral: false,
    language: "kn-IN",
    status: "pending_confirmation",
    record_version: 1,
    missing_fields: [],
    ...overrides,
  };
}

function activeState(): VoiceVisitState {
  let s = voiceVisitReducer(initialVoiceVisitState, { type: "start", clientVisitId: "visit-1" });
  s = voiceVisitReducer(s, {
    type: "server",
    event: { seq: 1, turn_id: 0, type: "session.started", session_id: "s1", stt_model: "prisma-v3.0" },
  });
  return s;
}

describe("voiceVisitReducer", () => {
  it("disables confirm before any read-back", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 1, type: "record.updated", record: makeRecord(), changed_fields: ["weight_kg"] },
    });
    expect(canConfirm(s)).toBe(false);
    expect(confirmBlockReason(s)).toContain("Waiting for read-back");
  });

  it("enables confirm only after read-back of the same version finishes", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 1, type: "record.updated", record: makeRecord({ record_version: 2 }), changed_fields: [] },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 3, turn_id: 1, type: "record.confirmation_requested", record_version: 2 },
    });
    expect(canConfirm(s)).toBe(false);
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "readback", recordVersion: 2 });
    expect(canConfirm(s)).toBe(true);
    expect(confirmBlockReason(s)).toBeNull();
  });

  it("ignores a playback acknowledgement for an older version", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 1, type: "record.updated", record: makeRecord({ record_version: 2 }), changed_fields: [] },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 3, turn_id: 1, type: "record.confirmation_requested", record_version: 2 },
    });
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "readback", recordVersion: 1 });
    expect(s.playedReadbackVersion).toBeNull();
    expect(canConfirm(s)).toBe(false);
  });

  it("clears confirmVersion and playback ack when a correction increments the version", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 1, type: "record.updated", record: makeRecord({ record_version: 1 }), changed_fields: [] },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 3, turn_id: 1, type: "record.confirmation_requested", record_version: 1 },
    });
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "readback", recordVersion: 1 });
    expect(canConfirm(s)).toBe(true);

    s = voiceVisitReducer(s, {
      type: "server",
      event: {
        seq: 4,
        turn_id: 2,
        type: "record.updated",
        record: makeRecord({ record_version: 2, weight_kg: 3 }),
        changed_fields: ["weight_kg"],
      },
    });
    expect(s.confirmVersion).toBeNull();
    expect(s.playedReadbackVersion).toBeNull();
    expect(canConfirm(s)).toBe(false);
  });

  it("blocks confirm with a reason when read-back audio fails or is missing", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 1, type: "record.updated", record: makeRecord(), changed_fields: [] },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 3, turn_id: 1, type: "record.confirmation_requested", record_version: 1 },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: {
        seq: 4,
        turn_id: 1,
        type: "agent.audio",
        purpose: "readback",
        text: "ತೂಕ...",
        audio_b64: null,
        mime_type: "audio/wav",
        record_version: 1,
      },
    });
    expect(s.readbackAudioFailed).toBe(true);
    expect(canConfirm(s)).toBe(false);
    expect(confirmBlockReason(s)).toContain("Read-back audio failed");
  });

  it("blocks confirm when required fields are still missing", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: {
        seq: 2,
        turn_id: 1,
        type: "record.updated",
        record: makeRecord({ missing_fields: ["next_visit_date"], next_visit_date: null }),
        changed_fields: [],
      },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 3, turn_id: 1, type: "record.confirmation_requested", record_version: 1 },
    });
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "readback", recordVersion: 1 });
    expect(canConfirm(s)).toBe(false);
    expect(confirmBlockReason(s)).toContain("missing fields");
  });

  it("ignores session.ended after the visit is saved", () => {
    let s = activeState();
    s = voiceVisitReducer(s, { type: "confirm_sent" });
    s = voiceVisitReducer(s, {
      type: "server",
      event: {
        seq: 5,
        turn_id: 2,
        type: "v2.visit.saved",
        visit_id: "v-123",
        person_public_id: "P-012",
        record_version: 1,
        confirmed_at: "2026-11-22T01:00:00Z",
        idempotent_replay: false,
      },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 6, turn_id: 2, type: "session.ended", reason: "cancelled", message: "Stopped" },
    });
    expect(s.phase).toBe("saved");
    expect(s.saved?.visit_id).toBe("v-123");
    expect(s.notice).toBeNull();
  });

  it("transitions to ended with the server message when session.ended arrives while active", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 0, type: "session.ended", reason: "revoked", message: "Access revoked" },
    });
    expect(s.phase).toBe("ended");
    expect(s.notice).toBe("Access revoked");
  });

  it("reconciles connection_lost while saving via receipt_found and receipt_missing", () => {
    let s = activeState();
    s = voiceVisitReducer(s, { type: "confirm_sent" });
    expect(s.phase).toBe("saving");
    const lost = voiceVisitReducer(s, { type: "connection_lost" });
    expect(lost.phase).toBe("save_unknown");

    const visit: V2VisitOut = {
      id: "v-999",
      client_visit_id: "visit-1",
      person_public_id: "P-012",
      household_public_id: "H-003",
      recorded_by: "Worker A",
      visit_type: "newborn",
      subject_population: "newborn",
      weight_kg: 3,
      vaccinations_due: null,
      next_visit_date: "2026-11-28",
      danger_signs: [],
      requires_phc_referral: false,
      rule_status: "demo_only_pending_clinical_review",
      ruleset_version: "rules-abc",
      extraction_source: "deterministic",
      record_version: 2,
      confirmed_at: "2026-11-22T01:05:00Z",
      is_demo_data: true,
    };
    const found = voiceVisitReducer(lost, { type: "receipt_found", visit });
    expect(found.phase).toBe("saved");
    expect(found.saved?.visit_id).toBe("v-999");

    const missing = voiceVisitReducer(lost, { type: "receipt_missing" });
    expect(missing.phase).toBe("ended");
    expect(missing.notice).toContain("Nothing was saved");
  });

  it("returns from saving to active on session.error", () => {
    let s = activeState();
    s = voiceVisitReducer(s, { type: "confirm_sent" });
    s = voiceVisitReducer(s, {
      type: "server",
      event: {
        seq: 4,
        turn_id: 1,
        type: "session.error",
        code: "READBACK_NOT_FINISHED",
        message: "Wait for read-back",
        retryable: true,
      },
    });
    expect(s.phase).toBe("active");
    expect(s.error).toBe("Wait for read-back");
  });

  it("checks boundMatches against household and person public IDs", () => {
    const bound: V2SessionBound = {
      seq: 1,
      turn_id: 0,
      type: "v2.session.bound",
      household_public_id: "H-003",
      person_public_id: "P-012",
      person_display_name: "Baby of Kavya Halli",
      visit_type: "newborn",
      client_visit_id: "visit-1",
    };
    expect(boundMatches(bound, "H-003", "P-012")).toBe(true);
    expect(boundMatches(bound, "H-004", "P-012")).toBe(false);
    expect(boundMatches(bound, "H-003", "P-011")).toBe(false);
    expect(boundMatches(null, "H-003", "P-012")).toBe(false);
  });

  it("provides 6 explicit visit type options with no default", () => {
    expect(VISIT_TYPE_OPTIONS.map((o) => o.value)).toEqual([
      "ANC",
      "PNC",
      "newborn",
      "immunisation",
      "routine",
      "unknown",
    ]);
    expect(VISIT_TYPE_OPTIONS).toHaveLength(6);
  });

  it("caps transcript lines at 30", () => {
    let s = activeState();
    for (let i = 1; i <= 35; i++) {
      s = voiceVisitReducer(s, {
        type: "server",
        event: { seq: i + 1, turn_id: i, type: "transcript.final", text: `line ${i}`, language: "kn-IN" },
      });
    }
    expect(s.lines).toHaveLength(30);
    expect(s.lines[0].text).toBe("line 6");
    expect(s.lines[29].text).toBe("line 35");
  });

  it("blocks confirm immediately when speech or a correction transcript starts", () => {
    let s = activeState();
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 2, turn_id: 1, type: "record.updated", record: makeRecord({ record_version: 1 }), changed_fields: [] },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 3, turn_id: 1, type: "record.confirmation_requested", record_version: 1 },
    });
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "readback", recordVersion: 1 });
    expect(canConfirm(s)).toBe(true);

    s = voiceVisitReducer(s, { type: "server", event: { seq: 4, turn_id: 2, type: "speech.started" } });
    expect(canConfirm(s)).toBe(false);
    expect(confirmBlockReason(s)).toContain("Processing spoken update");

    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 5, turn_id: 2, type: "transcript.final", text: "No, weight 55 kg", language: "en-IN" },
    });
    expect(canConfirm(s)).toBe(false);

    s = voiceVisitReducer(s, {
      type: "server",
      event: {
        seq: 6,
        turn_id: 2,
        type: "record.updated",
        record: makeRecord({ record_version: 2, weight_kg: 55 }),
        changed_fields: ["weight_kg"],
      },
    });
    s = voiceVisitReducer(s, {
      type: "server",
      event: { seq: 7, turn_id: 2, type: "record.confirmation_requested", record_version: 2 },
    });
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "readback", recordVersion: 2 });
    expect(canConfirm(s)).toBe(true);
  });

  it("shows the short disclosure greeting once per session and opens listening after playback", () => {
    let s = activeState();
    const disclosureEvent = {
      seq: 2,
      turn_id: 0,
      type: "agent.audio" as const,
      purpose: "disclosure" as const,
      text: "ನಮಸ್ಕಾರ, ನಾನು AI ಸಹಾಯಕ.",
      audio_b64: "UklGRg==",
      mime_type: "audio/wav",
      record_version: null,
    };
    s = voiceVisitReducer(s, { type: "server", event: disclosureEvent });
    expect(s.disclosureReceived).toBe(true);
    expect(s.disclosurePlayed).toBe(false);
    expect(s.lines).toHaveLength(1);
    expect(s.lines[0]).toMatchObject({ who: "agent", text: "ನಮಸ್ಕಾರ, ನಾನು AI ಸಹಾಯಕ." });

    // A duplicate disclosure event within the same session must not add a second bubble.
    s = voiceVisitReducer(s, { type: "server", event: { ...disclosureEvent, seq: 3 } });
    expect(s.lines).toHaveLength(1);

    // Completing disclosure playback enables immediate listening.
    s = voiceVisitReducer(s, { type: "clip_ended", purpose: "disclosure", recordVersion: null });
    expect(s.disclosurePlayed).toBe(true);

    // A brand new voice session resets the greeting state cleanly.
    const nextSession = voiceVisitReducer(s, { type: "start", clientVisitId: "visit-2" });
    expect(nextSession.disclosureReceived).toBe(false);
    expect(nextSession.disclosurePlayed).toBe(false);
    expect(nextSession.lines).toHaveLength(0);
  });
});
