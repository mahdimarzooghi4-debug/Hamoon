import type { BrowserPrincipal } from "../auth/oidc";
import {
  canUseAdminHealth,
  canUseLearningGovernance,
} from "../auth/access";
import { AppLink } from "../app/navigation";
import { Badge, EmptyState, Panel } from "../design-system/components";

export function RoleHomePage({
  principal,
}: {
  principal: BrowserPrincipal;
}) {
  const canUseGovernance = canUseLearningGovernance(principal);
  const canUseHealth = canUseAdminHealth(principal);

  return (
    <div className="page-stack">
      <header className="page-heading">
        <div>
          <span className="eyebrow">نشست سازمانی فعال</span>
          <h1>{principal.displayName ?? "کاربر سازمانی"}</h1>
          <p>
            رابط هامون فقط مسیرهایی را نمایش می‌دهد که با نقش فعلی سازگارند؛
            مرجع نهایی مجوز همچنان backend است.
          </p>
        </div>
        <Badge tone="accent">
          {principal.roles.length > 0
            ? principal.roles.join(" · ")
            : "بدون نقش محصول"}
        </Badge>
      </header>

      {canUseHealth ? (
        <Panel>
          <EmptyState
            title="کنسول سلامت عملیاتی آماده است"
            description="Data Health و Machine Health از read-modelهای persisted و بدون تغییر state محصول نمایش داده می‌شوند."
            action={
              <AppLink
                className="hm-button hm-button--primary"
                to="/admin/health"
              >
                ورود به سلامت سامانه
              </AppLink>
            }
          />
        </Panel>
      ) : null}

      {canUseGovernance ? (
        <Panel>
          <EmptyState
            title="کنسول یادگیری و حاکمیت آماده است"
            description="Dataset، Evaluation، Routing Policy و Promotion صریح انسانی از مسیر مدیریتی قابل دسترسی‌اند."
            action={
              <AppLink
                className="hm-button hm-button--primary"
                to="/admin/learning"
              >
                ورود به یادگیری و حاکمیت
              </AppLink>
            }
          />
        </Panel>
      ) : null}

      {!canUseHealth && !canUseGovernance ? (
        <Panel>
          <EmptyState
            title="برای این نقش workspace مستقلی در این نسخه تعریف نشده است"
            description="هیچ صفحه عملیاتی خارج از مجوز نقش فعلی mount نمی‌شود. برای دسترسی‌های بیشتر باید نقش و policy سمت سرور تغییر کند."
          />
        </Panel>
      ) : null}
    </div>
  );
}
