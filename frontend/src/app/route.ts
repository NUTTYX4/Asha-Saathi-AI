/** Which app a path shows: /v2 (and below) is ASHA SAATHI 2.0; everything else is Round 1. */
export function isV2Path(pathname: string): boolean {
  return /^\/v2(\/|$)/.test(pathname);
}
