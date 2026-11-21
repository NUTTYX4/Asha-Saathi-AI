import type { AgeOut, PersonOut } from "../../types/contracts";

/** Display text for API codes. Labels only: nothing here infers health status. */

export function ageLabel(age: AgeOut): string {
  if (age.basis === "unknown") return "Age not recorded";
  if (age.basis === "recorded_age") return `${age.years ?? "?"} years (recorded age)`;
  if (age.days != null) return age.days === 1 ? "1 day" : `${age.days} days`;
  if (age.months != null) return age.months === 1 ? "1 month" : `${age.months} months`;
  return `${age.years ?? "?"} years`;
}

export function codeLabel(code: string): string {
  return code.replace(/_in_law$/, "-in-law").replace(/_/g, " ");
}

const PROGRAMME_LABELS: Record<string, string> = {
  ANC: "ANC",
  PNC: "PNC",
  NEWBORN: "Newborn",
  IMMUNISATION: "Immunisation",
  NCD_FOLLOWUP: "NCD follow-up",
};

export function programmeLabel(code: string): string {
  return PROGRAMME_LABELS[code] ?? codeLabel(code);
}

export function activeProgrammes(p: PersonOut): string[] {
  return p.programmes.filter((e) => e.status === "active").map((e) => programmeLabel(e.programme));
}

export function relationshipLine(r: PersonOut["relationships"][number]): string {
  const type = codeLabel(r.relationship_type.replace(/_of$/, ""));
  return r.direction === "outgoing" ? `${type} of ${r.other_person_name}` : `${r.other_person_name} is their ${type}`;
}
