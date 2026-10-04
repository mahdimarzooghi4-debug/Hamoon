import { useAppPath } from "./navigation";
import { AppShell } from "../layout/AppShell";
import { HomePage } from "../pages/HomePage";
import { HouseholdPage } from "../pages/HouseholdPage";
import { HouseholdsPage } from "../pages/HouseholdsPage";
import { WorkQueuePage } from "../pages/WorkQueuePage";
import { LearningGovernancePage } from "../pages/LearningGovernancePage";
import { AuthCallbackPage } from "../pages/AuthCallbackPage";

export function App() {
  const path = useAppPath();

  let page = <HomePage />;
  if (path === "/work-queue") {
    page = <WorkQueuePage />;
  } else if (path === "/households") {
    page = <HouseholdsPage />;
  } else if (path.startsWith("/households/")) {
    page = <HouseholdPage householdId={path.slice("/households/".length)} />;
  } else if (path === "/admin/learning") {
    page = <LearningGovernancePage />;
  } else if (path === "/auth/callback") {
    page = <AuthCallbackPage />;
  }

  return <AppShell activePath={path}>{page}</AppShell>;
}
