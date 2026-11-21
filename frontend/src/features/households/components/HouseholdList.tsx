import { ChevronRight, CircleCheck, House } from "lucide-react";

import type { HouseholdPin } from "../../../types/contracts";
import { Badge } from "../../ui/primitives";

interface Props {
  pins: HouseholdPin[];
  highlightedId: string | null;
  confirmedId: string | null;
  onPick: (pin: HouseholdPin) => void;
}

/** The accessible list of households: always usable, with or without the map or GPS. */
export function HouseholdList({ pins, highlightedId, confirmedId, onPick }: Props) {
  if (pins.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-neutral-300 bg-surface px-4 py-5 text-center text-sm text-fg-2">
        No households to show.
      </p>
    );
  }
  return (
    <ul aria-label="Households" className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
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
              className={`flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 ${
                highlighted ? "bg-berry-50" : "hover:bg-neutral-50"
              }`}
            >
              <span
                aria-hidden="true"
                className={`grid size-11 shrink-0 place-items-center rounded-md ${
                  highlighted ? "bg-berry-600 text-white" : "bg-berry-50 text-berry-600"
                }`}
              >
                <House size={22} />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-lg leading-tight font-extrabold">{pin.public_id}</span>
                <span className="text-sm break-words text-fg-2">{pin.label}</span>
              </span>
              <span className="flex shrink-0 flex-col items-end gap-1 text-sm text-fg-2">
                <span className="font-semibold text-fg">{pin.member_count} members</span>
                <span className="text-xs">{pin.territory_code}</span>
                {confirmed && (
                  <Badge tone="success" icon={<CircleCheck size={12} />}>
                    Confirmed
                  </Badge>
                )}
              </span>
              <ChevronRight size={20} aria-hidden="true" className="shrink-0 text-fg-3" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
