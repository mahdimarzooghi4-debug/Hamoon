import { useEffect, useMemo, useRef, useState } from "react";

import { getAcceptedHistory, type AcceptedStateChange, type HouseholdFact } from "../api/familyData";
import { Button, EmptyState, ErrorState, LoadingState, Panel } from "../design-system/components";

type HistoryState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: AcceptedStateChange[]; nextBeforeVersion: number | null };

const formatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium", timeStyle: "short" });

function factValue(fact: HouseholdFact | undefined): string {
  if (!fact) return "مقدار در فهرست فعلی واقعیت‌ها موجود نیست";
  if (fact.value === null || fact.value === undefined) return "نامشخص";
  if (typeof fact.value === "boolean") return fact.value ? "بله" : "خیر";
  if (typeof fact.value === "string") return fact.value;
  return JSON.stringify(fact.value);
}

export function AcceptedStateHistoryPanel({
  householdId,
  factType,
  currentFactId,
  facts,
  refreshToken,
}: {
  householdId: string;
  factType: string;
  currentFactId: string;
  facts: HouseholdFact[];
  refreshToken: number;
}) {
  const [state, setState] = useState<HistoryState>({ kind: "loading" });
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const generationRef = useRef(0);
  const inFlightRef = useRef(false);
  const factsById = useMemo(() => new Map(facts.map((fact) => [fact.id, fact])), [facts]);

  useEffect(() => {
    const generation = ++generationRef.current;
    inFlightRef.current = false;
    setLoadingMore(false);
    setLoadError(false);
    setState({ kind: "loading" });
    void getAcceptedHistory(householdId, factType).then(
      (response) => {
        if (generation === generationRef.current) {
          setState({ kind: "ready", items: response.data, nextBeforeVersion: response.next_before_version });
        }
      },
      () => {
        if (generation === generationRef.current) setState({ kind: "error" });
      },
    );
    return () => { generationRef.current += 1; };
  }, [householdId, factType, refreshToken]);

  async function loadMore() {
    if (state.kind !== "ready" || state.nextBeforeVersion === null || inFlightRef.current) return;
    inFlightRef.current = true;
    setLoadingMore(true);
    setLoadError(false);
    const generation = generationRef.current;
    const cursor = state.nextBeforeVersion;
    try {
      const response = await getAcceptedHistory(householdId, factType, cursor);
      if (generation === generationRef.current) {
        setState((previous) => {
          if (previous.kind !== "ready" || previous.nextBeforeVersion !== cursor) return previous;
          return {
            kind: "ready",
            items: [...previous.items, ...response.data],
            nextBeforeVersion: response.next_before_version,
          };
        });
      }
    } catch {
      if (generation === generationRef.current) setLoadError(true);
    } finally {
      if (generation === generationRef.current) {
        inFlightRef.current = false;
        setLoadingMore(false);
      }
    }
  }

  return (
    <Panel>
      <div className="section-heading">
        <div>
          <span className="eyebrow">ردپای تصمیم‌های انسانی · فیگما 37:6493</span>
          <h2>تاریخچه پذیرش داده</h2>
        </div>
      </div>
      <p className="fact-caution">
        این فهرست از دفتر تغییرات Accepted State خوانده می‌شود؛ «پذیرفته‌شده در گذشته»
        لزوماً به معنی تغییر خودکار وضعیت اعتبارسنجی به SUPERSEDED نیست.
        تصمیم‌ها به ترتیب نسخه نمایش داده می‌شوند و مقدار قبلی حذف نشده است.
      </p>
      {state.kind === "loading" ? <LoadingState label="در حال دریافت تاریخچه تصمیم‌ها…" /> : null}
      {state.kind === "error" ? (
        <ErrorState title="تاریخچه دریافت نشد" description="بدون داده معتبر، تاریخچه‌ای حدس زده نمی‌شود." />
      ) : null}
      {state.kind === "ready" && state.items.length === 0 ? (
        <EmptyState title="تاریخچه پذیرش موجود نیست" description="برای این نوع واقعیت، تصمیم پذیرش ثبت‌شده‌ای بازگردانده نشد." />
      ) : null}
      {state.kind === "ready" && state.items.length > 0 ? (
        <div className="fact-decision-list">
          {state.items.map((item) => {
            const acceptedFact = factsById.get(item.new_fact_id);
            const priorFact = item.previous_fact_id ? factsById.get(item.previous_fact_id) : undefined;
            const isCurrent = item.new_fact_id === currentFactId && item.projection_version === state.items[0].projection_version;
            return (
              <article className="fact-decision-item" key={item.id}>
                <div className="fact-history-head">
                  <strong>نسخه پذیرش {item.projection_version.toLocaleString("fa-IR")}</strong>
                  <span className={isCurrent ? "fact-current-label" : "fact-past-label"}>
                    {isCurrent ? "داده پذیرفته‌شده فعلی" : "تصمیم پذیرش تاریخی"}
                  </span>
                </div>
                <div className="fact-two-col">
                  <div className="fact-readonly">
                    <span>مقدار پذیرفته‌شده در این تصمیم</span>
                    <strong>{factValue(acceptedFact)}</strong>
                    <small className="ltr-value">شناسه: {item.new_fact_id}</small>
                  </div>
                  <div className="fact-readonly">
                    <span>مقدار پذیرفته‌شده پیش از این تصمیم</span>
                    <strong>{item.previous_fact_id ? factValue(priorFact) : "پذیرش اولیه؛ بدون نسخه قبلی"}</strong>
                    {item.previous_fact_id ? <small className="ltr-value">شناسه: {item.previous_fact_id}</small> : null}
                  </div>
                </div>
                <div className="fact-history-meta">
                  <span>زمان تصمیم: {formatter.format(new Date(item.changed_at))}</span>
                  <span>تصمیم‌گیرنده (شناسه): <bdi dir="ltr">{item.changed_by}</bdi></span>
                </div>
                <div className="fact-decision-reason">
                  <strong>دلیل ثبت‌شده: {item.reason_code}</strong>
                  <p>{item.reason_text || "توضیح متنی برای این تصمیم ثبت نشده است."}</p>
                </div>
                <small className="ltr-value">شناسه رویداد ممیزی: {item.domain_event_id}</small>
              </article>
            );
          })}
          {state.nextBeforeVersion !== null ? (
            <div className="fact-more">
              <Button variant="secondary" disabled={loadingMore} onClick={() => void loadMore()}>
                {loadingMore ? "در حال دریافت…" : "نمایش تصمیم‌های قدیمی‌تر"}
              </Button>
              {loadError ? <span role="alert">دریافت صفحه بعد ناموفق بود؛ موارد موجود حفظ شدند.</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}
