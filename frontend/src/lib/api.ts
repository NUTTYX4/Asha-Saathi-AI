import type { AshaSaathiContracts, FollowUpItem, SavedVisit } from "../types/contracts";

export type ServerEvent = AshaSaathiContracts["server_event"];
export type ClientEvent = AshaSaathiContracts["client_event"];

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} failed: HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const api = {
  health: () => getJson<{ status: string; gnani_configured: boolean; stt_model: string; tts_model: string }>("/api/health"),
  visits: () => getJson<SavedVisit[]>("/api/visits"),
  followups: () => getJson<FollowUpItem[]>("/api/followups"),
};

export function sessionSocketUrl(): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/ws/session`;
}
