import { useEffect, useState, type ReactNode } from "react";

import { getReadiness, type HealthResponse } from "../api/health";
import { type AppPath, AppLink } from "../app/navigation";
import {
  canUseCasework,
  canUseLearningGovernance,
} from "../auth/access";
import {
  beginLogin,
  logout,
  type BrowserPrincipal,
} from "../auth/oidc";
import { Badge } from "../design-system/components";

export function AppShell({
  activePath,
  principal,
  children,
}: {
  activePath: AppPath;
  principal: BrowserPrincipal | null;
  children: ReactNode;
}) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const authenticated = principal !== null;
  const caseworkAllowed = canUseCasework(principal);
  const governanceAllowed = canUseLearningGovernance(principal);

  useEffect(() => {
    let mounted = true;
    getReadiness()
      .then((value) => {
        if (mounted) setHealth(value);
      })
      .catch(() => {
        if (mounted) setHealth(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const ready = health?.status === "ready";
  const householdsActive =
    activePath === "/households" || activePath.startsWith("/households/");
  const adminActive = activePath === "/admin/learning";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="topbar__identity">
            <div className="avatar" aria-hidden="true">م</div>
            <div>
              <strong>
                {principal?.displayName ??
                  (adminActive ? "کنسول مدیریت" : "کاربر سازمانی")}
              </strong>
              <span>
                {governanceAllowed
                  ? "مدیریت یادگیری و حاکمیت AI"
                  : caseworkAllowed
                    ? "مددکار پرونده"
                    : authenticated
                      ? "کاربر سازمانی"
                      : "هامون"}
              </span>
            </div>
          </div>

          <nav className="topbar__nav" aria-label="ناوبری اصلی">
            <AppLink
              className={activePath === "/" ? "topbar__link is-active" : "topbar__link"}
              to="/"
            >
              خانه
            </AppLink>
            {caseworkAllowed ? (
              <>
                <AppLink
                  className={householdsActive ? "topbar__link is-active" : "topbar__link"}
                  to="/households"
                >
                  پرونده‌ها
                </AppLink>
                <AppLink
                  className={
                    activePath === "/work-queue" ? "topbar__link is-active" : "topbar__link"
                  }
                  to="/work-queue"
                >
                  کارتابل
                </AppLink>
              </>
            ) : null}
            {governanceAllowed ? (
              <AppLink
                className={adminActive ? "topbar__link is-active" : "topbar__link"}
                to="/admin/learning"
              >
                یادگیری و حاکمیت
              </AppLink>
            ) : null}
          </nav>

          <div className="topbar__end">
            <div className="topbar__auth">
              {authenticated ? (
                <button
                  className="hm-button hm-button--quiet"
                  onClick={logout}
                  type="button"
                >
                  خروج
                </button>
              ) : (
                <button
                  className="hm-button hm-button--secondary"
                  onClick={() => void beginLogin(activePath)}
                  type="button"
                >
                  ورود سازمانی
                </button>
              )}
            </div>
            <div className="brand">
              <div className="brand__copy">
                <strong>هامون</strong>
                <span>ماشین توانمندسازی هوشمند</span>
              </div>
              <div className="brand__mark" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        </div>
        <div className="service-strip">
          <Badge tone={ready ? "success" : "warning"}>
            {ready ? "سامانه آماده است" : "وضعیت سامانه در حال بررسی"}
          </Badge>
        </div>
      </header>

      <main className="app-main">{children}</main>
    </div>
  );
}
