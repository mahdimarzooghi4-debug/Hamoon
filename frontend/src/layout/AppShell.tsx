import { useEffect, useState, type ReactNode } from "react";

import { getReadiness, type HealthResponse } from "../api/health";
import { type AppPath, AppLink } from "../app/navigation";
import {
  canUseAdminHealth,
  canUseCasework,
  canUseEmpowermentOverview,
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
  const healthAllowed = canUseAdminHealth(principal);
  const empowermentAllowed = canUseEmpowermentOverview(principal);

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
  const adminActive =
    activePath === "/admin/learning"
    || activePath === "/admin/health"
    || activePath === "/admin/empowerment";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__inner">
          <details
            className="topbar__menu"
            onClick={(event) => {
              if ((event.target as HTMLElement).closest("a, button")) {
                event.currentTarget.open = false;
              }
            }}
          >
            <summary className="topbar__profile">
              <span className="avatar" aria-hidden="true">م</span>
              <span className="topbar__profile-copy">
                <strong>
                  {principal?.displayName ??
                    (adminActive ? "کنسول مدیریت" : "کاربر سازمانی")}
                </strong>
                <span className="topbar__role">
                  {governanceAllowed
                    ? "مدیریت یادگیری و حاکمیت AI"
                    : healthAllowed
                      ? "پایش سلامت داده و ماشین"
                      : empowermentAllowed
                        ? "تحلیل تجمیعی توانمندسازی"
                        : caseworkAllowed
                          ? "مددکار پرونده"
                          : authenticated
                            ? "کاربر سازمانی"
                            : "هامون"}
                </span>
              </span>
              <span className="topbar__chevron" aria-hidden="true">⌄</span>
            </summary>

            <div className="topbar__popover">
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
                      className={activePath === "/work-queue" ? "topbar__link is-active" : "topbar__link"}
                      to="/work-queue"
                    >
                      کارتابل
                    </AppLink>
                  </>
                ) : null}
                {empowermentAllowed ? (
                  <AppLink
                    className={activePath === "/admin/empowerment" ? "topbar__link is-active" : "topbar__link"}
                    to="/admin/empowerment"
                  >
                    نمای توانمندسازی
                  </AppLink>
                ) : null}
                {healthAllowed ? (
                  <AppLink
                    className={activePath === "/admin/health" ? "topbar__link is-active" : "topbar__link"}
                    to="/admin/health"
                  >
                    سلامت سامانه
                  </AppLink>
                ) : null}
                {governanceAllowed ? (
                  <AppLink
                    className={activePath === "/admin/learning" ? "topbar__link is-active" : "topbar__link"}
                    to="/admin/learning"
                  >
                    یادگیری و حاکمیت
                  </AppLink>
                ) : null}
              </nav>
              <div className="topbar__auth">
                {authenticated ? (
                  <button className="hm-button hm-button--quiet" onClick={logout} type="button">
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
            </div>
          </details>

          <div className="brand">
            <div className="brand__copy">
              <strong>هامون</strong>
              <span>ماشین توانمندسازی هوشمند</span>
            </div>
            <svg className="brand__mark" viewBox="0 0 44 52" aria-hidden="true">
              <defs>
                <linearGradient id="hamoon-mark-fill" x1="6" y1="8" x2="39" y2="46" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#12DDE8" />
                  <stop offset=".48" stopColor="#1393DF" />
                  <stop offset="1" stopColor="#0B2D6B" />
                </linearGradient>
                <linearGradient id="hamoon-mark-edge" x1="7" y1="3" x2="38" y2="49" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#65F7FF" />
                  <stop offset=".58" stopColor="#16B8E1" />
                  <stop offset="1" stopColor="#1173C4" />
                </linearGradient>
              </defs>
              <path d="M22 3C31.8 3 39 6.3 39 10.7v30.6C39 45.7 31.8 49 22 49S5 45.7 5 41.3V10.7C5 6.3 12.2 3 22 3Z" fill="url(#hamoon-mark-fill)" opacity=".9" />
              <path d="M5.5 11C5.5 15.2 12.9 18.5 22 18.5S38.5 15.2 38.5 11M5.5 21C5.5 25.2 12.9 28.5 22 28.5S38.5 25.2 38.5 21M5.5 31C5.5 35.2 12.9 38.5 22 38.5S38.5 35.2 38.5 31M5.5 41C5.5 45.2 12.9 48.5 22 48.5S38.5 45.2 38.5 41" fill="none" stroke="url(#hamoon-mark-edge)" strokeWidth="2.4" />
              <path d="M9 14C15 10 17 8 22 8s8 2 13 5v9c-7-3-10-4-15-2-5 2-7 6-11 8v-9c3-2 4-4 0-5v0ZM9 35c5-2 7-6 12-8s8-1 14 2v8c-5-3-8-4-13-2s-8 5-13 8v-8Z" fill="none" stroke="#D7FBFF" strokeOpacity=".72" strokeWidth="1.25" />
              <path d="M22 5v42" stroke="#A5F7FF" strokeOpacity=".58" strokeWidth="1" />
            </svg>
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
