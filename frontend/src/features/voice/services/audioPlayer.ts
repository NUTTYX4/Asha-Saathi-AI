/**
 * Sequential playback of agent speech (base64 WAV from Timbre via the backend).
 * Barge-in: `cancel(turn)` stops current audio and drops queued items from older
 * turns. Danger alerts are never cut off.
 */

type Item = {
  buffer: AudioBuffer;
  turn: number;
  purpose: string;
  recordVersion: number | null;
  gain: number;
};

// Never cut off by barge-in: the AI disclosure (compliance) and danger referrals (safety).
const PROTECTED = new Set(["alert", "disclosure"]);

// Timbre audio arrives quiet (measured peak about -14 dBFS), so each clip is
// normalised to just under full scale. The phone's volume buttons then control the
// full range. Peak normalisation cannot clip; MAX_GAIN stops near-silence being blown up.
const TARGET_PEAK = 0.89; // about -1 dBFS
const MAX_GAIN = 6;

function normalisingGain(buffer: AudioBuffer): number {
  let peak = 0;
  for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
    const data = buffer.getChannelData(ch);
    for (let i = 0; i < data.length; i++) {
      const v = Math.abs(data[i]);
      if (v > peak) peak = v;
    }
  }
  return peak > 0 ? Math.min(MAX_GAIN, TARGET_PEAK / peak) : 1;
}

export class AgentAudioPlayer {
  private ctx: AudioContext;
  private queue: Item[] = [];
  private current: { source: AudioBufferSourceNode; item: Item } | null = null;
  private minTurn = 0;
  private closed = false;

  constructor(
    private onSpeakingChange: (speaking: boolean) => void,
    private onClipEnded?: (purpose: string, recordVersion: number | null) => void,
  ) {
    // Created from a user gesture (the start button) so autoplay policies allow it.
    this.ctx = new AudioContext();
  }

  async enqueue(
    audioB64: string,
    turn: number,
    purpose: string,
    recordVersion: number | null = null,
  ): Promise<void> {
    if (this.closed || (turn < this.minTurn && !PROTECTED.has(purpose))) return;
    const bytes = Uint8Array.from(atob(audioB64), (c) => c.charCodeAt(0));
    const buffer = await this.ctx.decodeAudioData(bytes.buffer);
    if (this.closed || (turn < this.minTurn && !PROTECTED.has(purpose))) return; // cancelled or closed while decoding
    const item: Item = { buffer, turn, purpose, recordVersion, gain: normalisingGain(buffer) };
    // Alerts jump the queue.
    if (purpose === "alert") this.queue.unshift(item);
    else this.queue.push(item);
    if (!this.current) this.playNext();
  }

  cancel(turn: number): void {
    this.minTurn = Math.max(this.minTurn, turn);
    this.queue = this.queue.filter((i) => PROTECTED.has(i.purpose));
    if (this.current && !PROTECTED.has(this.current.item.purpose)) {
      this.current.source.onended = null;
      this.current.source.stop();
      this.current = null;
      this.playNext();
    }
  }

  private playNext(): void {
    if (this.closed) {
      this.current = null;
      this.onSpeakingChange(false);
      return;
    }
    const item = this.queue.shift();
    if (!item) {
      this.current = null;
      this.onSpeakingChange(false);
      return;
    }
    const source = this.ctx.createBufferSource();
    source.buffer = item.buffer;
    const gain = this.ctx.createGain();
    gain.gain.value = item.gain;
    source.connect(gain).connect(this.ctx.destination);
    source.onended = () => {
      this.current = null;
      if (!this.closed) {
        this.onClipEnded?.(item.purpose, item.recordVersion);
        this.playNext();
      }
    };
    this.current = { source, item };
    this.onSpeakingChange(true);
    source.start();
  }

  async close(): Promise<void> {
    this.closed = true;
    this.queue = [];
    if (this.current) {
      this.current.source.onended = null;
      try {
        this.current.source.stop();
      } catch {
        // ignore if already stopped
      }
      this.current = null;
    }
    this.onSpeakingChange(false);
    await this.ctx.close();
  }
}
