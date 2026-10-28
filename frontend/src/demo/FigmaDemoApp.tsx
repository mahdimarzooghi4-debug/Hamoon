import { useEffect, useState } from "react";
import { FigmaHomeDemo } from "./FigmaHomeDemo";
import { FigmaQueueDemo } from "./FigmaQueueDemo";
import { FigmaHouseholdDemo } from "./FigmaHouseholdDemo";
import { FigmaIntakeDemo } from "./FigmaIntakeDemo";
import { FigmaQuestionBankAdminDemo } from "./FigmaQuestionBankAdminDemo";
import { FigmaIndicatorApprovalDemo } from "./FigmaIndicatorApprovalDemo";
import { FigmaObservationReviewDemo } from "./FigmaObservationReviewDemo";
import { observePersianDigits } from "./persianDigits";
import "./figma-demo-pages.css";

type DemoScreen = "home" | "household" | "queue" | "households" | "reassessment" | "registration" | "questions" | "review" | "indicator-review";
const screens: { id: DemoScreen; label: string; alt: string }[] = [
  { id: "home", label: "خانه", alt: "صفحه اصلی هامون" },
  { id: "household", label: "پرونده خانوار", alt: "پرونده هوشمند خانوار" },
  { id: "queue", label: "کارتابل", alt: "کارتابل مددکار" },
  { id: "households", label: "پرونده‌های من", alt: "فهرست پرونده‌های مددکار" },
  { id: "reassessment", label: "ارزیابی مجدد", alt: "شروع ارزیابی مجدد" },
  { id: "registration", label: "ثبت اطلاعات", alt: "ثبت اطلاعات مددکار" },
  { id: "questions", label: "مدیریت شاخص‌ها", alt: "مدیریت شاخص‌های مدل PGOR" },
  { id: "review", label: "بازبینی داده‌ها", alt: "بازبینی داده‌های PGOR" },
  { id: "indicator-review", label: "بازبینی شاخص‌ها", alt: "بازبینی تخصصی نسخه‌های شاخص" },
];

export function FigmaDemoApp() {
  const [screen, setScreen] = useState<DemoScreen>("home");
  const [image, setImage] = useState("");
  const [error, setError] = useState(false);
  const activeScreen = screens.find((item) => item.id === screen) ?? screens[0];

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    if (screen === "home" || screen === "household" || screen === "queue" || screen === "registration" || screen === "questions" || screen === "review" || screen === "indicator-review") {
      setImage("");
      setError(false);
      return;
    }
    let cancelled = false;
    setImage("");
    setError(false);
    fetch(`/demo-pages/${screen}.b64`)
      .then((response) => {
        if (!response.ok) throw new Error("DEMO_SCREEN_NOT_FOUND");
        return response.text();
      })
      .then((base64) => {
        if (!cancelled) setImage(`data:image/png;base64,${base64.trim()}`);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => { cancelled = true; };
  }, [screen]);

  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".fh-demo-shell");
    if (!root) return;
    return observePersianDigits(root);
  }, []);

  return (
    <div className="fh-demo-shell" lang="fa">
      {screen === "home" ? <FigmaHomeDemo /> :
        screen === "household" ? <FigmaHouseholdDemo /> :
          screen === "queue" ? <FigmaQueueDemo /> :
          screen === "registration" ? <FigmaIntakeDemo /> :
          screen === "questions" ? <FigmaQuestionBankAdminDemo /> :
            screen === "review" ? <FigmaObservationReviewDemo /> :
              screen === "indicator-review" ? <FigmaIndicatorApprovalDemo /> :
            <main className="fh-demo-screen" aria-label={activeScreen.alt}>
              {image ? <img className="fh-demo-screen__image" src={image} alt={activeScreen.alt} /> : null}
              {error ? <p className="fh-demo-screen__error">این صفحه‌ی نمایشی بارگذاری نشد. دوباره انتخابش کن.</p> : null}
            </main>}
      <nav className="fh-demo-nav" aria-label="صفحه‌های دمو">
        <span className="fh-demo-nav__label">دموی هامون</span>
        {screens.map((item) => (
          <button aria-current={screen === item.id ? "page" : undefined}
            className={screen === item.id ? "is-active" : ""} key={item.id}
            onClick={() => setScreen(item.id)} type="button">{item.label}</button>
        ))}
      </nav>
    </div>
  );
}
