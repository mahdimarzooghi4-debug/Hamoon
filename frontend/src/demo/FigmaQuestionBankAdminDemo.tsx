import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  groups,
  loadDemoIndicators,
  saveDemoIndicators,
  type DemoIndicator,
  type Group,
} from "./questionBank";

export function FigmaQuestionBankAdminDemo() {
  const [indicators, setIndicators] = useState<DemoIndicator[]>(loadDemoIndicators);
  const [filter, setFilter] = useState<Group | "ALL">("ALL");
  const [editing, setEditing] = useState<DemoIndicator | null>(null);
  const [notice, setNotice] = useState("");

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
          const changed = item.group !== editing.group
            || item.groupName !== editing.groupName
            || item.category !== category
            || item.guidance !== guidance
            || item.measurementMethod !== measurementMethod
            || item.score0Anchor !== score0Anchor
            || item.score50Anchor !== score50Anchor
            || item.score100Anchor !== score100Anchor
            || item.analysisUnitRule !== analysisUnitRule
            || JSON.stringify(item.evidenceSources) !== JSON.stringify(evidenceSources);
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
            draft: changed ? true : item.draft,
            revision: changed ? item.revision + 1 : item.revision,
          };
        })
        : [{ ...editing, category: editing.category.trim(), guidance: editing.guidance.trim(), measurementMethod: editing.measurementMethod.trim(), score0Anchor: editing.score0Anchor.trim(), score50Anchor: editing.score50Anchor.trim(), score100Anchor: editing.score100Anchor.trim(), analysisUnitRule: editing.analysisUnitRule, evidenceSources: editing.evidenceSources.map((source) => source.trim()).filter(Boolean), revision: 1 }, ...current];
    });
    setNotice("شاخص ذخیره شد؛ تغییر محتوا نسخهٔ تازه می‌سازد.");
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
      active: true,
      draft: true,
    });
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
        بازهٔ عددی دمو ۰ تا ۱۰۰ است. مدیر می‌تواند روش، لنگرهای ۰/۵۰/۱۰۰، سطح تحلیل و منبع‌های پیشنهادی هر شاخص را پیش‌نویس کند. تغییر آن نسخه را بالا می‌برد؛ تا تصویب تخصصی، هیچ‌کدام قاعدهٔ رسمی نیست و دمو امتیاز رسمی مدل تولید نمی‌کند.
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
              <small>روش سنجش: {indicator.measurementMethod || "تعریف نشده"} · لنگرهای ۰/۵۰/۱۰۰: {[indicator.score0Anchor, indicator.score50Anchor, indicator.score100Anchor].some(Boolean) ? "پیش‌نویس دارد" : "تعریف نشده"} · سطح تحلیل: {indicator.analysisUnitRule === "UNRESOLVED" ? "تعریف نشده" : indicator.analysisUnitRule === "MEMBER" ? "عضو" : indicator.analysisUnitRule === "HOUSEHOLD" ? "خانوار" : "منطقه"} (پیش‌نویس) · منابع پیشنهادی: {indicator.evidenceSources.length ? indicator.evidenceSources.length + " مورد" : "تعریف نشده"}</small>
              <small>نسخهٔ {indicator.revision} · {indicator.draft ? "پیش‌نویس برای بازبینی" : "تنظیم‌شده"}</small>
            </div>
            <div className="fh-question-admin__actions">
              <button onClick={() => setEditing(indicator)} type="button">ویرایش</button>
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
