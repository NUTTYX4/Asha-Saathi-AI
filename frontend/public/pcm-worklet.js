// AudioWorklet: downsample mic audio to 16 kHz mono PCM s16le and post
// exact 512-sample (1,024-byte) frames, the format Gnani Prisma expects.
class PcmDownsampler extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000; // sampleRate is the AudioContext rate
    this.acc = 0;
    this.sum = 0;
    this.count = 0;
    this.frame = new Int16Array(512);
    this.index = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    for (let i = 0; i < channel.length; i++) {
      // Box-filter decimation: average the input samples that map to one output sample.
      this.sum += channel[i];
      this.count += 1;
      this.acc += 1;
      if (this.acc >= this.ratio) {
        const s = Math.max(-1, Math.min(1, this.sum / this.count));
        this.frame[this.index++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        this.acc -= this.ratio;
        this.sum = 0;
        this.count = 0;
        if (this.index === this.frame.length) {
          this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
          this.frame = new Int16Array(512);
          this.index = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-downsampler", PcmDownsampler);
