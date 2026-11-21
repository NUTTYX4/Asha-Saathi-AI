import type { HouseholdPin } from "../../../types/contracts";

interface Props {
  pins: HouseholdPin[];
  highlightedId: string | null;
  confirmedId: string | null;
  onPick: (pin: HouseholdPin) => void;
}

/** The accessible list of households: always usable, with or without the map or GPS. */
export function HouseholdList({ pins, highlightedId, confirmedId, onPick }: Props) {
  if (pins.length === 0) return <p className="px-1 text-sm text-ink-soft">No households to show.</p>;
  return (
    <ul className="flex flex-col gap-2" aria-label="Households">
      {pins.map((pin) => {
        const confirmed = pin.id === confirmedId;
        const highlighted = pin.id === highlightedId;
        return (
          <li key={pin.id}>
            <button
              type="button"
              onClick={() => onPick(pin)}
              aria-pressed={highlighted}
              data-household={pin.public_id}
              className={`flex min-h-14 w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left ${
                highlighted ? "border-rose bg-rose/5" : "border-rule bg-sheet"
              }`}
            >
              <span className="flex flex-col">
                <span className="font-display text-lg font-bold leading-tight">{pin.public_id}</span>
                <span className="text-xs text-ink-soft">{pin.label}</span>
              </span>
              <span className="flex flex-col items-end text-xs text-ink-soft">
                <span>{pin.member_count} members</span>
                <span>{pin.territory_code}</span>
                {confirmed && <span className="font-semibold text-leaf">Confirmed</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
