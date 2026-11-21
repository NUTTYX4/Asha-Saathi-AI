import { useEffect, useRef } from "react";

import type { TranscriptLine } from "../hooks/useVoiceSession";

/** Finalized speech segments from Prisma (no partials exist) and agent replies. */
export function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Block body: newer Chromium returns a value from scrollIntoView, and React
    // would treat a returned non-function as a broken cleanup.
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lines.length]);

  return (
    <section aria-label="Conversation" className="max-h-56 overflow-y-auto rounded-2xl bg-sheet p-4 ring-1 ring-rule">
      {lines.length === 0 ? (
        <p className="text-ink-soft">ಮಾತನಾಡಿದ್ದು ಇಲ್ಲಿ ಕಾಣಿಸುತ್ತದೆ · Your speech appears here</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {lines.map((line) => (
            <li
              key={line.id}
              className={`enter max-w-[90%] rounded-xl px-3 py-2 text-[1.05rem] leading-relaxed ${
                line.who === "worker" ? "self-end bg-ink text-white" : "self-start bg-paper text-ink"
              }`}
            >
              {line.text}
            </li>
          ))}
        </ul>
      )}
      <div ref={endRef} />
    </section>
  );
}
