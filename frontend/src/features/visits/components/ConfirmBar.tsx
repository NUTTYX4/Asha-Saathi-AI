interface Props {
  version: number;
  onConfirm: () => void;
}

/** Tap fallback for confirmation (voice "ಹೌದು" is primary). Sends the read-back version. */
export function ConfirmBar({ version, onConfirm }: Props) {
  return (
    <div className="enter flex items-center gap-3 rounded-2xl bg-sheet p-3 ring-2 ring-leaf">
      <p className="flex-1 text-sm leading-snug">
        ಸರಿ ಇದ್ದರೆ <strong>“ಹೌದು”</strong> ಎನ್ನಿ ಅಥವಾ ಒತ್ತಿ. ತಪ್ಪಿದ್ದರೆ ಸರಿಯಾದ ಮಾಹಿತಿ ಹೇಳಿ.
        <span className="block text-xs text-ink-soft">Say “haudu” or tap to save version {version}. Speak to correct.</span>
      </p>
      <button
        type="button"
        onClick={onConfirm}
        className="min-h-12 rounded-xl bg-leaf px-5 font-display text-lg font-bold text-white transition-transform duration-(--duration-micro) ease-(--ease-tactile) active:scale-[0.97] focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        ಹೌದು, ಉಳಿಸಿ
      </button>
    </div>
  );
}
