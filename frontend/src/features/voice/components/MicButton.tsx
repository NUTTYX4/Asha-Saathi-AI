interface Props {
  active: boolean;
  connecting: boolean;
  listening: boolean;
  onStart: () => void;
  onStop: () => void;
}

/** Large thumb-zone control. Ring animates only while the agent is listening. */
export function MicButton({ active, connecting, listening, onStart, onStop }: Props) {
  const label = active ? "ಭೇಟಿ ನಿಲ್ಲಿಸಿ · Stop" : connecting ? "ಸಂಪರ್ಕಿಸುತ್ತಿದೆ…" : "ಭೇಟಿ ಆರಂಭಿಸಿ · Start visit";
  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={active ? onStop : onStart}
        disabled={connecting}
        aria-pressed={active}
        aria-label={label}
        className="relative grid size-24 place-items-center rounded-full bg-rose text-white shadow-[0_10px_24px_-8px_rgb(140_29_74/0.6)] transition-transform duration-(--duration-micro) ease-(--ease-tactile) active:scale-[0.97] disabled:opacity-60 focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-ink"
      >
        {active && listening && (
          <span aria-hidden className="listening-ring absolute inset-0 rounded-full border-4 border-rose" />
        )}
        {active ? (
          <svg viewBox="0 0 24 24" className="size-9" aria-hidden>
            <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="size-10" aria-hidden>
            <path
              fill="currentColor"
              d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z"
            />
          </svg>
        )}
      </button>
      <span className="font-display text-base font-medium">{label}</span>
    </div>
  );
}
