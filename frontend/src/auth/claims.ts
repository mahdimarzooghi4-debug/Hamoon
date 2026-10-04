export const HAMOON_ROLES = [
  "CASEWORKER",
  "MANAGER",
  "ADMIN",
  "SYSTEM_INTEGRATION",
  "PROVIDER_INTEGRATION",
  "AI_RUNTIME",
  "SECURITY_AUDITOR",
] as const;

export type HamoonRole = (typeof HAMOON_ROLES)[number];

const knownRoles = new Set<string>(HAMOON_ROLES);

function stringRoles(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

export function extractHamoonRoles(
  claims: Record<string, unknown>,
): HamoonRole[] {
  const names = new Set<string>();

  for (const role of stringRoles(claims.roles)) {
    names.add(role);
  }

  const realmAccess =
    typeof claims.realm_access === "object" && claims.realm_access !== null
      ? (claims.realm_access as Record<string, unknown>)
      : null;

  for (const role of stringRoles(realmAccess?.roles)) {
    names.add(role);
  }

  return [...names].filter(
    (role): role is HamoonRole => knownRoles.has(role),
  );
}
