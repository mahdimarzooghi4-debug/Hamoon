import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";

import { navigate } from "../app/navigation";
import { HouseholdPage } from "./HouseholdPage";
import { HouseholdFactsPage } from "./HouseholdFactsPage";

/**
 * Route-addressable correction sheet over the real authorized household view.
 * Background data comes only from HouseholdPage's existing API and stays inert.
 */
export function HouseholdFactsOverlayPage({ householdId }: { householdId: string }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [topOffset, setTopOffset] = useState(76);
  const householdPath = `/households/${householdId}` as const;

  useEffect(() => {
    const header = document.querySelector<HTMLElement>(".topbar");
    const priorInert = header?.inert ?? false;
    const priorAriaHidden = header?.getAttribute("aria-hidden") ?? null;
    const priorOverflow = document.body.style.overflow;
    const recalculate = () => setTopOffset(Math.max(0, header?.getBoundingClientRect().bottom ?? 0));

    recalculate();
    window.addEventListener("resize", recalculate);
    document.body.style.overflow = "hidden";
    // The header is visually retained like Figma, but cannot be interacted with
    // while the modal is open. Restore previous DOM state on any navigation.
    if (header) {
      header.inert = true;
      header.setAttribute("aria-hidden", "true");
    }
    const animation = requestAnimationFrame(() => dialogRef.current?.focus());
    return () => {
      cancelAnimationFrame(animation);
      window.removeEventListener("resize", recalculate);
      document.body.style.overflow = priorOverflow;
      if (header) {
        header.inert = priorInert;
        if (priorAriaHidden === null) header.removeAttribute("aria-hidden");
        else header.setAttribute("aria-hidden", priorAriaHidden);
      }
    };
  }, []);

  function operationBusy(): boolean {
    return dialogRef.current?.querySelector(".fact-workspace")?.getAttribute("data-operation-busy") === "true";
  }

  function close() {
    if (!operationBusy()) navigate(householdPath);
  }

  function onDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusables = [...dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter((element) => element.getClientRects().length > 0 && !element.closest("[inert]"));
    if (focusables.length === 0) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="fact-route" style={{ "--fact-overlay-top": `${topOffset}px` } as CSSProperties}>
      <div className="fact-route__background" aria-hidden="true" inert data-fact-background="real-household">
        <HouseholdPage householdId={householdId} />
      </div>
      <div className="fact-route__backdrop" aria-hidden="true" />
      <section
        className="fact-route__dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="اصلاح و اعتبارسنجی اطلاعات"
        tabIndex={-1}
        onKeyDown={onDialogKeyDown}
      >
        <button
          className="fact-route__close"
          type="button"
          aria-label="بستن پنل اصلاح"
          onClick={close}
        >×</button>
        <HouseholdFactsPage householdId={householdId} />
      </section>
    </div>
  );
}
