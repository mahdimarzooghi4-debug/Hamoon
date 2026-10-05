export type PrincipalLike = {
  roles: readonly string[];
} | null;

export type RouteAccess =
  | "allowed"
  | "authentication-required"
  | "forbidden";

const CASEWORK_PATHS = new Set(["/work-queue", "/households"]);
const LEARNING_ADMIN_PATHS = new Set(["/admin/learning"]);
const HEALTH_ADMIN_PATHS = new Set(["/admin/health"]);
const EMPOWERMENT_PATHS = new Set(["/admin/empowerment"]);

export function hasRole(
  principal: PrincipalLike,
  role: string,
): boolean {
  return principal?.roles.includes(role) ?? false;
}

export function canUseCasework(principal: PrincipalLike): boolean {
  return hasRole(principal, "CASEWORKER");
}

export function canUseLearningGovernance(
  principal: PrincipalLike,
): boolean {
  return hasRole(principal, "ADMIN");
}

export function canUseAdminHealth(principal: PrincipalLike): boolean {
  return (
    hasRole(principal, "ADMIN")
    || hasRole(principal, "SECURITY_AUDITOR")
  );
}

export function canUseEmpowermentOverview(
  principal: PrincipalLike,
): boolean {
  return (
    hasRole(principal, "MANAGER")
    || hasRole(principal, "ADMIN")
  );
}

export function accessForPath(
  path: string,
  principal: PrincipalLike,
): RouteAccess {
  if (path === "/" || path === "/auth/callback") {
    return "allowed";
  }

  const requiresCasework =
    CASEWORK_PATHS.has(path) || path.startsWith("/households/");
  const requiresLearningAdmin = LEARNING_ADMIN_PATHS.has(path);
  const requiresHealthAdmin = HEALTH_ADMIN_PATHS.has(path);
  const requiresEmpowerment = EMPOWERMENT_PATHS.has(path);

  if (
    !requiresCasework
    && !requiresLearningAdmin
    && !requiresHealthAdmin
    && !requiresEmpowerment
  ) {
    return "allowed";
  }
  if (principal === null) {
    return "authentication-required";
  }
  if (requiresCasework && !canUseCasework(principal)) {
    return "forbidden";
  }
  if (requiresLearningAdmin && !canUseLearningGovernance(principal)) {
    return "forbidden";
  }
  if (requiresHealthAdmin && !canUseAdminHealth(principal)) {
    return "forbidden";
  }
  if (requiresEmpowerment && !canUseEmpowermentOverview(principal)) {
    return "forbidden";
  }
  return "allowed";
}
