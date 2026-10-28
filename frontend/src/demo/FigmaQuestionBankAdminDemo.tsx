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
        ? current.map((item) => item.id === editing.id ? {
          ...editing,
          category: editing.category.trim(),
          guidance: editing.guidance.trim(),
        } : item)
        : [{ ...editing, category: editing.category.trim(), guidance: editing.guidance.trim() }, ...current];
    });
    setNotice("شاخص و راهنمای ثبت در نسخهٔ نمایشی ذخیره شد.");
    setEditing(null);
  }

  function addIndicator() {
    const group = filter === "ALL" ? "P" : filter;
    const groupName = groups.find((item) => item.id === group)!.name;
    setEditing({
      id: `custom-${Date.now()}`,
      group,
      groupName,
      category: "",
      guidance: "",
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
        بازهٔ عددی دمو ۰ تا ۱۰۰ است. روش علمی تعیین عدد و نگاشت آن به امتیاز PGOR هنوز باید تأیید شود؛ این دمو امتیاز رسمی مدل تولید نمی‌کند.
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
              <textarea required rows={3} value={editing.guidance} onChange={(event) => setEditing({ ...editing, guidance: event.target.value })} placeholder="منبع یا شیوهٔ سنجش مورد انتظار را برای بازبینی توضیح دهید" />
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
              <small>{indicator.draft ? "پیش‌نویس برای بازبینی" : "تنظیم‌شده"}</small>
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
