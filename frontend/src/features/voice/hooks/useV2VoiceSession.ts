import { useCallback, useEffect, useReducer, useRef } from "react";

import type { ServerEvent } from "../../../lib/api";
import { ApiError, apiV2, isUnauthorized, type V2ClientEvent, v2SessionSocketUrl } from "../../../lib/apiV2";
import type { VisitType } from "../../../types/contracts";
import { startCapture, type StopCapture } from "../services/audioCapture";
import { AgentAudioPlayer } from "../services/audioPlayer";
import {
  boundMatches,
  canConfirm,
  initialVoiceVisitState,
  type VoiceVisitAction,
  voiceVisitReducer,
} from "../v2/voiceVisit";

export interface StartV2VoiceParams {
  householdId: string;
  personId: string;
  householdPublicId: string;
  personPublicId: string;
  visitType: VisitType;
}

const POST_SAVE_CLOSE_MS = 4_000;

export function useV2VoiceSession(onSessionLost?: () => void) {
  const [state, rawDispatch] = useReducer(voiceVisitReducer, initialVoiceVisitState);
  const stateRef = useRef(state);
  const wsRef = useRef<WebSocket | null>(null);
  const playerRef = useRef<AgentAudioPlayer | null>(null);
  const stopCaptureRef = useRef<StopCapture | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const expectedRef = useRef<{ householdPublicId: string; personPublicId: string } | null>(null);
  const protectedAudioPlayingRef = useRef(false);

  const dispatch = useCallback((action: VoiceVisitAction) => {
    stateRef.current = voiceVisitReducer(stateRef.current, action);
    rawDispatch(action);
  }, []);

  const send = useCallback((event: V2ClientEvent) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(event));
    }
  }, []);

  const stopMic = useCallback(async () => {
    const stop = stopCaptureRef.current;
    stopCaptureRef.current = null;
    if (stop) await stop().catch(() => undefined);
  }, []);

  const teardown = useCallback(async () => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    await stopMic();
    protectedAudioPlayingRef.current = false;
    const player = playerRef.current;
    playerRef.current = null;
    if (player) await player.close().catch(() => undefined);
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState <= WebSocket.OPEN) {
      ws.close();
    }
  }, [stopMic]);

  const start = useCallback(
    (params: StartV2VoiceParams) => {
      if (wsRef.current) return;
      const clientVisitId = crypto.randomUUID();
      expectedRef.current = {
        householdPublicId: params.householdPublicId,
        personPublicId: params.personPublicId,
      };
      protectedAudioPlayingRef.current = false;
      dispatch({ type: "start", clientVisitId });

      // Created directly inside the tap handler so mobile autoplay policies allow playback.
      playerRef.current = new AgentAudioPlayer(
        (speaking) => dispatch({ type: "speaking", speaking }),
        (purpose, recordVersion) => {
          if (purpose === "disclosure" || purpose === "alert") {
            protectedAudioPlayingRef.current = false;
          }
          dispatch({ type: "clip_ended", purpose, recordVersion });
          if (purpose === "disclosure") {
            send({ type: "playback.completed", purpose: "disclosure", record_version: null });
          } else if (purpose === "readback") {
            send({ type: "playback.completed", purpose: "readback", record_version: recordVersion });
          }
        },
      );

      const ws = new WebSocket(v2SessionSocketUrl());
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        send({
          type: "v2.session.start",
          household_id: params.householdId,
          person_id: params.personId,
          client_visit_id: clientVisitId,
          visit_type: params.visitType,
        });
      };

      ws.onmessage = (msg) => {
        if (wsRef.current !== ws || typeof msg.data !== "string") return;
        let event: ServerEvent;
        try {
          event = JSON.parse(msg.data) as ServerEvent;
        } catch {
          return;
        }
        if (event.type === "agent.audio" && event.purpose === "disclosure" && stateRef.current.disclosureReceived) {
          return;
        }
        dispatch({ type: "server", event });

        if (event.type === "session.started") {
          void startCapture((frame) => {
            if (
              wsRef.current === ws &&
              ws.readyState === WebSocket.OPEN &&
              stateRef.current.disclosurePlayed &&
              !protectedAudioPlayingRef.current
            ) {
              ws.send(frame);
            }
          })
            .then((stop) => {
              if (wsRef.current !== ws) {
                void stop().catch(() => undefined);
                return;
              }
              stopCaptureRef.current = stop;
            })
            .catch((err) => {
              dispatch({
                type: "local_end",
                notice: `ಮೈಕ್ ಸಿಗಲಿಲ್ಲ / Microphone unavailable: ${(err as Error).message}`,
              });
              send({ type: "session.cancel" });
              void teardown();
            });
        } else if (event.type === "v2.session.bound") {
          const exp = expectedRef.current;
          if (exp && !boundMatches(event, exp.householdPublicId, exp.personPublicId)) {
            send({ type: "session.cancel" });
            dispatch({
              type: "local_end",
              notice: "Server bound a different person; visit cancelled.",
            });
            void teardown();
          }
        } else if (event.type === "agent.audio") {
          if (event.audio_b64) {
            if (event.purpose === "disclosure" || event.purpose === "alert") {
              protectedAudioPlayingRef.current = true;
            }
            playerRef.current
              ?.enqueue(event.audio_b64, event.turn_id, event.purpose, event.record_version ?? null)
              .catch(() => {
                if (event.purpose === "disclosure" || event.purpose === "alert") {
                  protectedAudioPlayingRef.current = false;
                }
                dispatch({ type: "clip_failed", purpose: event.purpose });
              });
          }
        } else if (event.type === "agent.audio.cancel") {
          playerRef.current?.cancel(event.turn_id);
        } else if (event.type === "v2.visit.saved") {
          void stopMic();
          closeTimerRef.current = window.setTimeout(() => {
            void teardown();
          }, POST_SAVE_CLOSE_MS);
        } else if (event.type === "session.ended") {
          void teardown();
        }
      };

      ws.onerror = () => {
        // onclose handles final connection cleanup and state transitions.
      };

      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        const current = stateRef.current;
        const wasSaving = current.phase === "saving";
        const activeVisitId = current.clientVisitId;
        dispatch({ type: "connection_lost" });
        void teardown();
        if (wasSaving && activeVisitId) {
          void apiV2
            .visitReceipt(activeVisitId)
            .then((visit) => {
              if (stateRef.current.clientVisitId === activeVisitId) {
                dispatch({ type: "receipt_found", visit });
              }
            })
            .catch((err) => {
              if (stateRef.current.clientVisitId !== activeVisitId) return;
              if (isUnauthorized(err)) {
                onSessionLost?.();
                return;
              }
              if (err instanceof ApiError && err.status === 404) {
                dispatch({ type: "receipt_missing" });
              } else {
                dispatch({ type: "receipt_unknown" });
              }
            });
        }
      };
    },
    [dispatch, onSessionLost, send, stopMic, teardown],
  );

  const confirm = useCallback(() => {
    const current = stateRef.current;
    if (!canConfirm(current) || current.confirmVersion === null) return;
    const version = current.confirmVersion;
    dispatch({ type: "confirm_sent" });
    send({ type: "record.confirm", record_version: version });
  }, [dispatch, send]);

  const replayReadback = useCallback(() => {
    send({ type: "readback.request" });
  }, [send]);

  const cancel = useCallback(() => {
    send({ type: "session.cancel" });
    dispatch({ type: "local_end", notice: "Visit cancelled. Nothing was saved." });
    void teardown();
  }, [dispatch, send, teardown]);

  const reset = useCallback(() => {
    void teardown();
    dispatch({ type: "reset" });
  }, [dispatch, teardown]);

  useEffect(() => {
    return () => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && stateRef.current.phase !== "saved") {
        try {
          ws.send(JSON.stringify({ type: "session.cancel" } satisfies V2ClientEvent));
        } catch {
          // ignore close errors on unmount
        }
      }
      void teardown();
    };
  }, [teardown]);

  return { state, start, confirm, replayReadback, cancel, reset };
}
