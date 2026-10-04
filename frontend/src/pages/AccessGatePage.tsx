import { beginLogin } from "../auth/oidc";
import { AppLink, type AppPath } from "../app/navigation";
import { Button, EmptyState, Panel } from "../design-system/components";

export function AccessGatePage({
  kind,
  returnTo,
}: {
  kind: "authentication-required" | "forbidden";
  returnTo: AppPath;
}) {
  return (
    <div className="page-stack">
      <Panel>
        {kind === "authentication-required" ? (
          <EmptyState
            title="ورود سازمانی لازم است"
            description="این بخش فقط پس از احراز هویت OIDC و دریافت نقش سازمانی قابل استفاده است."
            action={
              <Button onClick={() => void beginLogin(returnTo)}>
                ورود سازمانی
              </Button>
            }
          />
        ) : (
          <EmptyState
            title="دسترسی این نقش به این بخش مجاز نیست"
            description="نمایش این صفحه در رابط کاربری متوقف شده است؛ مجوز نهایی همچنان روی API و به‌صورت server-side enforce می‌شود."
            action={
              <AppLink className="hm-button hm-button--secondary" to="/">
                بازگشت به خانه
              </AppLink>
            }
          />
        )}
      </Panel>
    </div>
  );
}
