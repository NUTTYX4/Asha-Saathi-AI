"""Export canonical JSON Schemas from the Pydantic models into /contracts.

The frontend generates its TypeScript types from these files
(frontend: `npm run gen:types`). Run from backend/:
    .venv\\Scripts\\python -m scripts.export_contracts
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, TypeAdapter  # noqa: E402

from app.core.config import REPO_ROOT  # noqa: E402
from app.schemas.events import ClientEvent, ServerEvent  # noqa: E402
from app.schemas.visit import FollowUpItem, SavedVisit, VisitRecord  # noqa: E402


class Contracts(BaseModel):
    """Root container so one schema file holds every shared type."""

    visit_record: VisitRecord
    saved_visit: SavedVisit
    follow_up_item: FollowUpItem
    server_event: ServerEvent
    client_event: ClientEvent


def _strip_property_titles(node: object) -> None:
    """Pydantic titles every field; json2ts would emit an alias type per title."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for prop in props.values():
                if isinstance(prop, dict):
                    prop.pop("title", None)
        for value in node.values():
            _strip_property_titles(value)
    elif isinstance(node, list):
        for value in node:
            _strip_property_titles(value)


def main() -> None:
    out = REPO_ROOT / "contracts" / "contracts.schema.json"
    # Serialization mode: fields with defaults are always present on the wire, so
    # they are marked required (exact TS discriminated unions on `type`).
    schema = TypeAdapter(Contracts).json_schema(mode="serialization")
    _strip_property_titles(schema)
    schema["title"] = "AshaSaathiContracts"
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
