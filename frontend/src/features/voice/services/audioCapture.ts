/** Microphone capture -> 16 kHz PCM s16le frames of 1,024 bytes (see public/pcm-worklet.js). */

export type StopCapture = () => Promise<void>;

export async function startCapture(onFrame: (frame: ArrayBuffer) => void): Promise<StopCapture> {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone needs HTTPS (or localhost) and a supported browser.");
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true, // keeps the agent's own voice out of the STT stream
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const ctx = new AudioContext();
  await ctx.audioWorklet.addModule("/pcm-worklet.js");
  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "pcm-downsampler");
  node.port.onmessage = (event: MessageEvent<ArrayBuffer>) => onFrame(event.data);

  // Route through a muted gain so the graph is pulled without echoing the mic.
  const mute = ctx.createGain();
  mute.gain.value = 0;
  source.connect(node).connect(mute).connect(ctx.destination);

  return async () => {
    node.port.onmessage = null;
    source.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    await ctx.close();
  };
}
