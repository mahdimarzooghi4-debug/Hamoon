import { accessForPath, canUseCasework } from "../auth/access";
import { browserPrincipal } from "../auth/oidc";
import { AppShell } from "../layout/AppShell";
import { AccessGatePage } from "../pages/AccessGatePage";
import { AdminHealthPage } from "../pages/AdminHealthPage";
import { AuthCallbackPage } from "../pages/AuthCallbackPage";
import { HomePage } from "../pages/HomePage";
import { HouseholdPage } from "../pages/HouseholdPage";
import { HouseholdsPage } from "../pages/HouseholdsPage";
import { LearningGovernancePage } from "../pages/LearningGovernancePage";
import { RoleHomePage } from "../pages/RoleHomePage";
import { WorkQueuePage } from "../pages/WorkQueuePage";
import { useAppPath } from "./navigation";

export function App() {
  const path = useAppPath();
  const principal = browserPrincipal();
  const access = accessForPath(path, principal);

  let page;
  if (path === "/auth/callback") {
    page = <AuthCallbackPage />;
  } else if (access !== "allowed") {
    page = <AccessGatePage kind={access} returnTo={path} />;
  } else if (path === "/work-queue") {
    page = <WorkQueuePage />;
  } else if (path === "/households") {
    page = <HouseholdsPage />;
  } else if (path.startsWith("/households/")) {
    page = <HouseholdPage householdId={path.slice("/households/".length)} />;
  } else if (path === "/admin/learning") {
    page = <LearningGovernancePage />;
  } else if (path === "/admin/health") {
    page = <AdminHealthPage />;
  } else if (principal !== null && !canUseCasework(principal)) {
    page = <RoleHomePage principal={principal} />;
  } else {
    page = <HomePage />;
  }

  return (
    <AppShell activePath={path} principal={principal}>
      {page}
    </AppShell>
  );
}
