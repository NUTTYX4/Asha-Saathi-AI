/**
 * Sequential playback of agent speech (base64 WAV from Timbre via the backend).
 * Barge-in: `cancel(turn)` stops current audio and drops queued items from older
 * turns. Danger alerts are never cut off.
 */

type Item = { buffer: AudioBuffer; turn: number; purpose: string };

// Never cut off by barge-in: the AI disclosure (compliance) and danger referrals (safety).
const PROTECTED = new Set(["alert", "disclosure"]);

export class AgentAudioPlayer {
  private ctx: AudioContext;
  private queue: Item[] = [];
  private current: { source: AudioBufferSourceNode; item: Item } | null = null;
  private minTurn = 0;

  constructor(private onSpeakingChange: (speaking: boolean) => void) {
    // Created from a user gesture (the start button) so autoplay policies allow it.
    this.ctx = new AudioContext();
  }

  async enqueue(audioB64: string, turn: number, purpose: string): Promise<void> {
    if (turn < this.minTurn && !PROTECTED.has(purpose)) return;
    const bytes = Uint8Array.from(atob(audioB64), (c) => c.charCodeAt(0));
    const buffer = await this.ctx.decodeAudioData(bytes.buffer);
    if (turn < this.minTurn && !PROTECTED.has(purpose)) return; // cancelled while decoding
    const item = { buffer, turn, purpose };
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
    const item = this.queue.shift();
    if (!item) {
      this.current = null;
      this.onSpeakingChange(false);
      return;
    }
    const source = this.ctx.createBufferSource();
    source.buffer = item.buffer;
    source.connect(this.ctx.destination);
    source.onended = () => {
      this.current = null;
      this.playNext();
    };
    this.current = { source, item };
    this.onSpeakingChange(true);
    source.start();
  }

  async close(): Promise<void> {
    this.queue = [];
    this.current?.source.stop();
    await this.ctx.close();
  }
}
