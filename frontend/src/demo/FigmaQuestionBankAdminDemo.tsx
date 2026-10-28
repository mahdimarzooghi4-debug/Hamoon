import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  groups,
  loadDemoIndicators,
  saveDemoIndicators,
  type ApprovalStatus,
  type DemoIndicator,
  type DemoIndicatorSnapshot,
  type Group,
} from "./questionBank";

const approvalLabels: Record<ApprovalStatus, string> = {
  DRAFT: "پیش‌نویس",
  IN_REVIEW: "در بازبینی تخصصی",
  APPROVED: "مصوب",
  CHANGES_REQUESTED: "نیازمند اصلاح",
};

function snapshotIndicator(item: DemoIndicator): DemoIndicatorSnapshot {
  return {
    revision: item.revision,
    category: item.category,
    guidance: item.guidance,
    measurementMethod: item.measurementMethod,
    score0Anchor: item.score0Anchor,
    score50Anchor: item.score50Anchor,
    score100Anchor: item.score100Anchor,
    analysisUnitRule: item.analysisUnitRule,
    evidenceSources: [...item.evidenceSources],
    evidencePeriodGuidance: item.evidencePeriodGuidance,
    householdAggregationGuidance: item.householdAggregationGuidance,
  };
}

export function FigmaQuestionBankAdminDemo() {
  const [indicators, setIndicators] = useState<DemoIndicator[]>(loadDemoIndicators);
  const [filter, setFilter] = useState<Group | "ALL">("ALL");
  const [editing, setEditing] = useState<DemoIndicator | null>(null);
  const [notice, setNotice] = useState("");
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});

  useEffect(() => saveDemoIndicators(indicators), [indicators]);

  const visible = useMemo(
    () => indicators.filter((item) => filter === "ALL" || item.group === filter),
    [filter, indicators],
  );

  function saveIndicator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || !editing.category.trim() || !editing.guidance.trim()) return;
    setIndicators((current) => {
      const exists = current.some((item) => item.id === editing.id);
      return exists
        ? current.map((item) => {
          if (item.id !== editing.id) return item;
          const category = editing.category.trim();
          const guidance = editing.guidance.trim();
          const measurementMethod = editing.measurementMethod.trim();
          const score0Anchor = editing.score0Anchor.trim();
          const score50Anchor = editing.score50Anchor.trim();
          const score100Anchor = editing.score100Anchor.trim();
          const analysisUnitRule = editing.analysisUnitRule;
          const evidenceSources = editing.evidenceSources.map((source) => source.trim()).filter(Boolean);
          const evidencePeriodGuidance = editing.evidencePeriodGuidance.trim();
          const householdAggregationGuidance = editing.householdAggregationGuidance.trim();
          const changed = item.group !== editing.group
            || item.groupName !== editing.groupName
            || item.category !== category
            || item.guidance !== guidance
            || item.measurementMethod !== measurementMethod
            || item.score0Anchor !== score0Anchor
            || item.score50Anchor !== score50Anchor
            || item.score100Anchor !== score100Anchor
            || item.analysisUnitRule !== analysisUnitRule
            || JSON.stringify(item.evidenceSources) !== JSON.stringify(evidenceSources)
            || item.evidencePeriodGuidance !== evidencePeriodGuidance
            || item.householdAggregationGuidance !== householdAggregationGuidance;
          return {
            ...editing,
            category,
            guidance,
            measurementMethod,
            score0Anchor,
            score50Anchor,
            score100Anchor,
            analysisUnitRule,
            evidenceSources,
            evidencePeriodGuidance,
            householdAggregationGuidance,
            draft: changed ? true : item.draft,
            revision: changed ? item.revision + 1 : item.revision,
            approvalStatus: changed ? "DRAFT" : item.approvalStatus,
            reviewNote: changed ? "" : item.reviewNote,
            approvalHistory: changed
              ? [...item.approvalHistory, { status: "DRAFT", revision: item.revision + 1, note: "نسخه ویرایش شد و باید دوباره بررسی شود.", at: new Date().toISOString() }]
              : item.approvalHistory,
          };
        })
        : [{ ...editing, category: editing.category.trim(), guidance: editing.guidance.trim(), measurementMethod: editing.measurementMethod.trim(), score0Anchor: editing.score0Anchor.trim(), score50Anchor: editing.score50Anchor.trim(), score100Anchor: editing.score100Anchor.trim(), analysisUnitRule: editing.analysisUnitRule, evidenceSources: editing.evidenceSources.map((source) => source.trim()).filter(Boolean), evidencePeriodGuidance: editing.evidencePeriodGuidance.trim(), householdAggregationGuidance: editing.householdAggregationGuidance.trim(), revision: 1, approvalStatus: "DRAFT", approvedRevision: null, approvedSnapshot: null, reviewNote: "", approvalHistory: [] }, ...current];
    });
    setNotice("پیش‌نویس ذخیره شد؛ تغییر محتوا نسخهٔ تازه می‌سازد و تأیید قبلی را برای نسخهٔ جدید معتبر نمی‌کند.");
    setEditing(null);
  }

  function addIndicator() {
    const group = filter === "ALL" ? "P" : filter;
    const groupName = groups.find((item) => item.id === group)!.name;
    setEditing({
      id: `custom-${Date.now()}`,
      group,
      groupName,
      revision: 1,
      category: "",
      guidance: "",
      measurementMethod: "",
      score0Anchor: "",
      score50Anchor: "",
      score100Anchor: "",
      analysisUnitRule: "UNRESOLVED",
      evidenceSources: [],
      evidencePeriodGuidance: "",
      householdAggregationGuidance: "",
      active: true,
      draft: true,
      approvalStatus: "DRAFT",
      approvedRevision: null,
      approvedSnapshot: null,
      reviewNote: "",
      approvalHistory: [],
    });
  }

  function setApproval(indicator: DemoIndicator, status: ApprovalStatus, note = "") {
    const event = { status, revision: indicator.revision, note, at: new Date().toISOString() };
    setIndicators((current) => current.map((item) => item.id !== indicator.id ? item : ({
      ...item,
      approvalStatus: status,
      draft: status !== "APPROVED",
      approvedRevision: status === "APPROVED" ? item.revision : item.approvedRevision,
      approvedSnapshot: status === "APPROVED" ? snapshotIndicator(item) : item.approvedSnapshot,
      reviewNote: status === "CHANGES_REQUESTED" ? note : "",
      approvalHistory: [...item.approvalHistory, event],
    })));
    setReviewNotes((current) => ({ ...current, [indicator.id]: "" }));
    setNotice(status === "IN_REVIEW"
      ? `نسخهٔ ${indicator.revision} برای بازبینی فرستاده شد.`
      : status === "APPROVED"
        ? `نسخهٔ ${indicator.revision} تأیید شد؛ تصمیم و snapshot نسخه در همین مرورگر ثبت شد.`
        : "نسخه برای اصلاح برگشت خورد؛ پس از اصلاح باید دوباره برای بازبینی فرستاده شود.");
  }

  function toggleActive(indicator: DemoIndicator) {
    setIndicators((current) => current.map((item) =>
      item.id === indicator.id ? { ...item, active: !item.active } : item,
    ));
    setNotice(indicator.active
      ? "شاخص از فرم ثبت فعال خارج شد؛ امکان بازگردانی آن هست."
      : "شاخص دوباره به فرم ثبت فعال اضافه شد.");
  }

  return (
    <main className="fh-question-admin" dir="rtl" aria-label="مدیریت شاخص‌های هامون">
      <header className="fh-question-admin__header">
        <div>
          <span className="fh-intake__eyebrow">پنل مدیریت · نسخهٔ نمایشی</span>
          <h1>شاخص‌های ثبت دادهٔ PGOR</h1>
          <p>مددکار شاخص‌ها را می‌بیند و دادهٔ عددی ثبت می‌کند؛ متن زیر فقط راهنمای ثبت است و پرسشی برای طرح با خانواده نیست.</p>
        </div>
        <button className="fh-question-admin__add" onClick={addIndicator} type="button">＋ افزودن شاخص</button>
      </header>

      <div className="fh-question-admin__notice" role="note">
        بازهٔ عددی دمو ۰ تا ۱۰۰ است. مدیر می‌تواند روش، لنگرهای ۰/۵۰/۱۰۰، سطح تحلیل، منبع‌های پیشنهادی، بازه یا تازگی شواهد و قاعدهٔ تجمیع نتیجهٔ عضو در سطح خانوار را پیش‌نویس کند. تغییر آن نسخه را بالا می‌برد؛ هر نسخه باید جداگانه بازبینی شود. این گردش در دمو و همین مرورگر است و جایگزین احراز نقش یا تصویب واقعی تخصصی نیست؛ تا تصویب، قاعدهٔ رسمی یا امتیاز مدل تولید نمی‌شود.
      </div>

      <div className="fh-question-admin__tabs" role="tablist" aria-label="دسته‌های PGOR">
        <button className={filter === "ALL" ? "is-active" : ""} onClick={() => setFilter("ALL")} type="button">
          همهٔ دسته‌ها <span>{indicators.length}</span>
        </button>
        {groups.map((group) => (
          <button
            className={filter === group.id ? "is-active" : ""}
            key={group.id}
            onClick={() => setFilter(group.id)}
            type="button"
          >
            {group.id} · {group.name}
            <span>{indicators.filter((item) => item.group === group.id).length}</span>
          </button>
        ))}
      </div>

      {notice ? <p className="fh-question-admin__toast" role="status">{notice}</p> : null}

      {editing ? (
        <form className="fh-question-admin__editor" onSubmit={saveIndicator}>
          <div className="fh-question-admin__editor-head">
            <div>
              <small>{editing.id.startsWith("custom-") ? "شاخص تازه" : "ویرایش شاخص"}</small>
              <h2>مشخصات ثبت</h2>
            </div>
            <button aria-label="بستن فرم" onClick={() => setEditing(null)} type="button">×</button>
          </div>
          <div className="fh-question-admin__fields">
            <label>دستهٔ مدل
              <select value={editing.group} onChange={(event) => {
                const group = event.target.value as Group;
                setEditing({ ...editing, group, groupName: groups.find((item) => item.id === group)!.name });
              }}>
                {groups.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}
              </select>
            </label>
            <label>نام شاخص
              <input required value={editing.category} onChange={(event) => setEditing({ ...editing, category: event.target.value })} placeholder="مثلاً ثبات درآمد" />
            </label>
            <label className="is-wide">راهنمای ثبت برای مددکار
              <textarea required rows={3} value={editing.guidance} onChange={(event) => setEditing({ ...editing, guidance: event.target.value })} placeholder="چه مدرکی را برای این شاخص ثبت کند" />
            </label>
            <label className="is-wide">روش پیشنهادی سنجش (پیش‌نویس)
              <textarea rows={3} value={editing.measurementMethod} onChange={(event) => setEditing({ ...editing, measurementMethod: event.target.value })} placeholder="متغیر و روش محاسبه را برای بازبینی تخصصی بنویسید" />
            </label>
            <label>لنگر نمرهٔ ۰ (پیش‌نویس)
              <textarea rows={2} value={editing.score0Anchor} onChange={(event) => setEditing({ ...editing, score0Anchor: event.target.value })} placeholder="تعریف نمرهٔ صفر" />
            </label>
            <label>لنگر نمرهٔ ۵۰ (پیش‌نویس)
              <textarea rows={2} value={editing.score50Anchor} onChange={(event) => setEditing({ ...editing, score50Anchor: event.target.value })} placeholder="تعریف نقطهٔ میانی" />
            </label>
            <label>لنگر نمرهٔ ۱۰۰ (پیش‌نویس)
              <textarea rows={2} value={editing.score100Anchor} onChange={(event) => setEditing({ ...editing, score100Anchor: event.target.value })} placeholder="تعریف نمرهٔ کامل" />
            </label>
            <label>سطح تحلیل مورد انتظار (پیش‌نویس)
              <select value={editing.analysisUnitRule} onChange={(event) => setEditing({ ...editing, analysisUnitRule: event.target.value as DemoIndicator["analysisUnitRule"] })}>
                <option value="UNRESOLVED">هنوز تعیین نشده</option>
                <option value="MEMBER">عضو خانوار</option>
                <option value="HOUSEHOLD">کل خانوار</option>
                <option value="AREA">محیط منطقه</option>
              </select>
            </label>
            <label className="is-wide">منبع‌های شواهد پیشنهادی (پیش‌نویس، هر مورد یک خط)
              <textarea rows={4} value={editing.evidenceSources.join("\n")} onChange={(event) => setEditing({ ...editing, evidenceSources: event.target.value.split("\n").map((source) => source.trim()).filter(Boolean) })} placeholder="مثلاً گزارش بازدید\nسامانهٔ رسمی خدمت" />
            </label>
            <label className="is-wide">قاعدهٔ تجمیع دادهٔ عضو در سطح خانوار (در صورت نیاز، پیش‌نویس)
              <textarea rows={2} value={editing.householdAggregationGuidance} onChange={(event) => setEditing({ ...editing, householdAggregationGuidance: event.target.value })} placeholder="روش را فقط پس از تعریف و تصویب تخصصی بنویسید؛ محاسبه خودکار نیست" />
            </label>
            <label className="is-wide">بازه یا تازگی شواهد مورد انتظار (پیش‌نویس)
              <textarea rows={2} value={editing.evidencePeriodGuidance} onChange={(event) => setEditing({ ...editing, evidencePeriodGuidance: event.target.value })} placeholder="مثلاً دورهٔ گزارش یا حداکثر سن مدرک؛ پس از بازبینی تخصصی" />
            </label>
          </div>
          <div className="fh-question-admin__editor-actions">
            <button className="fh-question-admin__add" type="submit">ذخیرهٔ پیش‌نویس</button>
            <button className="fh-question-admin__cancel" onClick={() => setEditing(null)} type="button">انصراف</button>
          </div>
        </form>
      ) : null}

      <section className="fh-question-admin__list" aria-label="فهرست شاخص‌ها">
        {visible.map((indicator, index) => (
          <article className={`fh-question-admin__item ${indicator.active ? "" : "is-inactive"}`} key={indicator.id}>
            <div className="fh-question-admin__index">{String(index + 1).padStart(2, "0")}</div>
            <div className="fh-question-admin__copy">
              <div className="fh-question-admin__meta">
                <span>{indicator.group} · {indicator.groupName}</span>
                <b>{indicator.category}</b>
              </div>
              <p>{indicator.guidance}</p>
              <small>روش سنجش: {indicator.measurementMethod || "تعریف نشده"} · لنگرهای ۰/۵۰/۱۰۰: {[indicator.score0Anchor, indicator.score50Anchor, indicator.score100Anchor].some(Boolean) ? "پیش‌نویس دارد" : "تعریف نشده"} · سطح تحلیل: {indicator.analysisUnitRule === "UNRESOLVED" ? "تعریف نشده" : indicator.analysisUnitRule === "MEMBER" ? "عضو" : indicator.analysisUnitRule === "HOUSEHOLD" ? "خانوار" : "منطقه"} (پیش‌نویس) · منابع پیشنهادی: {indicator.evidenceSources.length ? indicator.evidenceSources.length + " مورد" : "تعریف نشده"} · دوره/تازگی: {indicator.evidencePeriodGuidance ? "پیش‌نویس دارد" : "تعریف نشده"} · تجمیع خانوار: {indicator.householdAggregationGuidance ? "پیش‌نویس دارد" : "تعریف نشده"}</small>
              <small>نسخهٔ جاری {indicator.revision} · وضعیت: {approvalLabels[indicator.approvalStatus]}{indicator.approvedRevision ? ` · آخرین نسخهٔ مصوب: ${indicator.approvedRevision}` : " · هنوز نسخهٔ مصوب ندارد"}</small>
              {indicator.reviewNote ? <small>یادداشت بازبین: {indicator.reviewNote}</small> : null}
              <details className="fh-question-admin__history">
                <summary>تاریخچهٔ بازبینی ({indicator.approvalHistory.length})</summary>
                {indicator.approvalHistory.length ? <ul>{indicator.approvalHistory.slice().reverse().map((event, eventIndex) => (
                  <li key={`${event.revision}-${event.status}-${event.at}-${eventIndex}`}>
                    نسخهٔ {event.revision} · {approvalLabels[event.status]} · {new Date(event.at).toLocaleString("fa-IR")}
                    {event.note ? ` · ${event.note}` : ""}
                  </li>
                ))}</ul> : <small>هنوز تصمیمی ثبت نشده است.</small>}
              </details>
            </div>
            <div className="fh-question-admin__actions">
              <button onClick={() => setEditing(indicator)} type="button">ویرایش</button>
              {indicator.approvalStatus === "DRAFT" || indicator.approvalStatus === "CHANGES_REQUESTED" ? (
                <button onClick={() => setApproval(indicator, "IN_REVIEW")} type="button">ارسال برای بازبینی</button>
              ) : null}
              {indicator.approvalStatus === "IN_REVIEW" ? (
                <>
                  <button onClick={() => setApproval(indicator, "APPROVED")} type="button">تأیید تخصصی نسخه</button>
                  <label className="fh-question-admin__review-note">دلیل برگشت برای اصلاح
                    <textarea rows={2} value={reviewNotes[indicator.id] ?? ""} onChange={(event) => setReviewNotes((current) => ({ ...current, [indicator.id]: event.target.value }))} placeholder="برای بازگشت، دلیل روشن بنویسید" />
                  </label>
                  <button disabled={!(reviewNotes[indicator.id] ?? "").trim()} onClick={() => setApproval(indicator, "CHANGES_REQUESTED", (reviewNotes[indicator.id] ?? "").trim())} type="button">برگشت برای اصلاح</button>
                </>
              ) : null}
              <button className={indicator.active ? "is-danger" : ""} onClick={() => toggleActive(indicator)} type="button">
                {indicator.active ? "حذف از فرم" : "فعال‌سازی"}
              </button>
            </div>
          </article>
        ))}
        {visible.length === 0 ? <p className="fh-question-admin__empty">هنوز شاخصی ثبت نشده است.</p> : null}
      </section>
      <footer className="fh-question-admin__footer">تغییرات دمو فقط در حافظهٔ این مرورگر ذخیره می‌شوند؛ ذخیره‌سازی سمت سرور هنوز پیاده نشده است.</footer>
    </main>
  );
}
