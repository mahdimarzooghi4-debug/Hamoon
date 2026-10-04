import { useAppPath } from "./navigation";
import { AppShell } from "../layout/AppShell";
import { HomePage } from "../pages/HomePage";
import { WorkQueuePage } from "../pages/WorkQueuePage";

export function App() {
  const path = useAppPath();

  return (
    <AppShell activePath={path}>
      {path === "/work-queue" ? <WorkQueuePage /> : <HomePage />}
    </AppShell>
  );
}
