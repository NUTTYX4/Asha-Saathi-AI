import { useCallback, useEffect, useRef, useState } from "react";

import { sessionSocketUrl, type ClientEvent, type ServerEvent } from "../../../lib/api";
import type { AlertRaised, RecordSaved, SessionState, VisitRecord } from "../../../types/contracts";
import { AgentAudioPlayer } from "../services/audioPlayer";
import { startCapture, type StopCapture } from "../services/audioCapture";

export type Connection = "idle" | "connecting" | "open" | "closed";

export interface TranscriptLine {
  id: number;
  who: "worker" | "agent";
  text: string;
}

export interface VoiceSessionView {
  connection: Connection;
  sessionState: SessionState;
  record: VisitRecord | null;
  changedFields: string[];
  lines: TranscriptLine[];
  alerts: AlertRaised[];
  agentSpeaking: boolean;
  confirmVersion: number | null;
  lastSaved: RecordSaved | null;
  sttModel: string | null;
  error: string | null;
}

const INITIAL: VoiceSessionView = {
  connection: "idle",
  sessionState: "idle",
  record: null,
  changedFields: [],
  lines: [],
  alerts: [],
  agentSpeaking: false,
  confirmVersion: null,
  lastSaved: null,
  sttModel: null,
  error: null,
};

export function useVoiceSession() {
  const [view, setView] = useState<VoiceSessionView>(INITIAL);
  const wsRef = useRef<WebSocket | null>(null);
  const stopCaptureRef = useRef<StopCapture | null>(null);
  const playerRef = useRef<AgentAudioPlayer | null>(null);
  const lineId = useRef(0);
  const disclosureSeenRef = useRef(false);
  const protectedAudioPlayingRef = useRef(false);

  const patch = useCallback((update: Partial<VoiceSessionView> | ((v: VoiceSessionView) => Partial<VoiceSessionView>)) => {
    setView((v) => ({ ...v, ...(typeof update === "function" ? update(v) : update) }));
  }, []);

  const addLine = useCallback(
    (who: TranscriptLine["who"], text: string) =>
      patch((v) => ({ lines: [...v.lines.slice(-30), { id: ++lineId.current, who, text }] })),
    [patch],
  );

  const send = useCallback((event: ClientEvent) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(event));
  }, []);

  const teardown = useCallback(async () => {
    const stop = stopCaptureRef.current;
    stopCaptureRef.current = null;
    protectedAudioPlayingRef.current = false;
    disclosureSeenRef.current = false;
    if (stop) await stop().catch(() => undefined);
    await playerRef.current?.close().catch(() => undefined);
    playerRef.current = null;
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
  }, []);

  const handleEvent = useCallback(
    async (event: ServerEvent) => {
      switch (event.type) {
        case "session.started":
          patch({ sttModel: event.stt_model ?? null });
          try {
            stopCaptureRef.current = await startCapture((frame) => {
              const ws = wsRef.current;
              if (ws?.readyState === WebSocket.OPEN && !protectedAudioPlayingRef.current) ws.send(frame);
            });
          } catch (err) {
            patch({ error: `ಮೈಕ್ ಸಿಗಲಿಲ್ಲ / Microphone unavailable: ${(err as Error).message}` });
            await teardown();
            patch({ connection: "closed", sessionState: "error" });
          }
          break;
        case "state.changed":
          patch({ sessionState: event.state });
          break;
        case "speech.started":
          break;
        case "transcript.final":
          addLine("worker", event.text);
          break;
        case "record.updated":
          patch((v) => ({
            record: event.record,
            changedFields: event.changed_fields,
            confirmVersion: event.record.status === "pending_confirmation" ? v.confirmVersion : null,
          }));
          break;
        case "clarification.requested":
          break;
        case "alert.raised":
          patch((v) => ({ alerts: [...v.alerts, event] }));
          break;
        case "agent.audio":
          if (event.purpose === "disclosure") {
            if (disclosureSeenRef.current) break;
            disclosureSeenRef.current = true;
          }
          addLine("agent", event.text);
          if (event.audio_b64) {
            if (event.purpose === "disclosure" || event.purpose === "alert") {
              protectedAudioPlayingRef.current = true;
            }
            playerRef.current?.enqueue(event.audio_b64, event.turn_id, event.purpose).catch((err) => {
              if (event.purpose === "disclosure" || event.purpose === "alert") {
                protectedAudioPlayingRef.current = false;
              }
              patch({ error: `Audio playback failed: ${(err as Error).message}` });
            });
          }
          break;
        case "agent.audio.cancel":
          playerRef.current?.cancel(event.turn_id);
          break;
        case "record.confirmation_requested":
          patch({ confirmVersion: event.record_version });
          break;
        case "record.saved":
          patch({ lastSaved: event, confirmVersion: null, alerts: [] });
          break;
        case "session.error":
          patch({ error: `${event.code}: ${event.message}` });
          break;
      }
    },
    [addLine, patch, teardown],
  );

  const start = useCallback(() => {
    if (wsRef.current) return;
    disclosureSeenRef.current = false;
    protectedAudioPlayingRef.current = false;
    setView({ ...INITIAL, connection: "connecting" });
    // Created inside the tap handler so mobile autoplay rules allow playback.
    playerRef.current = new AgentAudioPlayer(
      (speaking) => patch({ agentSpeaking: speaking }),
      (purpose) => {
        if (purpose === "disclosure" || purpose === "alert") {
          protectedAudioPlayingRef.current = false;
        }
      },
    );
    const ws = new WebSocket(sessionSocketUrl());
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;
    ws.onopen = () => {
      patch({ connection: "open" });
      send({ type: "session.start" });
    };
    ws.onmessage = (msg) => {
      if (typeof msg.data !== "string") return;
      void handleEvent(JSON.parse(msg.data) as ServerEvent);
    };
    ws.onerror = () => patch({ error: "ಸರ್ವರ್ ಸಂಪರ್ಕ ವಿಫಲ / Connection to server failed" });
    ws.onclose = () => {
      void teardown();
      patch({ connection: "closed", agentSpeaking: false });
    };
  }, [handleEvent, patch, send, teardown]);

  const stop = useCallback(() => {
    send({ type: "session.stop" });
    void teardown();
    patch({ connection: "closed", sessionState: "idle", agentSpeaking: false });
  }, [patch, send, teardown]);

  const confirm = useCallback(() => {
    if (view.confirmVersion !== null) send({ type: "record.confirm", record_version: view.confirmVersion });
  }, [send, view.confirmVersion]);

  useEffect(() => () => void teardown(), [teardown]);

  return { view, start, stop, confirm };
}
