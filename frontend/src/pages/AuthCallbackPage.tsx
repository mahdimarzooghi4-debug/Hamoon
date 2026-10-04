import { useEffect, useState } from "react";

import { beginLogin, completeLoginFromCallback } from "../auth/oidc";
import {
  Button,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type State =
  | { kind: "working" }
  | { kind: "error"; message: string };

export function AuthCallbackPage() {
  const [state, setState] = useState<State>({ kind: "working" });

  useEffect(() => {
    let active = true;
    completeLoginFromCallback()
      .then((returnTo) => {
        if (active) window.location.replace(returnTo);
      })
      .catch((error: unknown) => {
        if (!active) return;
        const message =
          error instanceof Error && error.message.includes("STATE_INVALID")
            ? "پاسخ ورود قابل اعتماد نبود یا نشست ورود منقضی شده است."
            : "تکمیل ورود سازمانی انجام نشد.";
        setState({ kind: "error", message });
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="auth-callback-page">
      <Panel className="auth-callback-card">
        {state.kind === "working" ? (
          <LoadingState label="در حال تکمیل ورود سازمانی…" />
        ) : (
          <ErrorState
            title="ورود تکمیل نشد"
            description={state.message}
            action={
              <Button onClick={() => void beginLogin("/")}>
                شروع دوباره ورود
              </Button>
            }
          />
        )}
      </Panel>
    </div>
  );
}
