import { useState, type FormEvent } from "react";

type DimensionCode = "P" | "G" | "O" | "R";
type DemoEntry = {
  id: number;
  dimension: DimensionCode;
  score: string;
  source: string;
  effectiveAt: string;
};

const dimensions: { code: DimensionCode; name: string }[] = [
  { code: "P", name: "بُعد P" },
  { code: "G", name: "بُعد G" },
  { code: "O", name: "بُعد O" },
  { code: "R", name: "بُعد R" },
];

export function FigmaIntakeDemo() {
  const [dimension, setDimension] = useState<DimensionCode>("P");
  const [score, setScore] = useState("");
  const [source, setSource] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [entries, setEntries] = useState<DemoEntry[]>([]);
  const [notice, setNotice] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!score || !source || !effectiveAt) return;
    setEntries((current) => [
      { id: Date.now(), dimension, score, source, effectiveAt },
      ...current,
    ]);
    setScore("");
    setSource("");
    setEffectiveAt("");
    setNotice("نمونه فقط در حافظه این صفحه ثبت شد؛ با بستن یا تازه‌سازی صفحه پاک می‌شود.");
  }

  return (
    <main className="fh-intake" aria-label="دموی ثبت اطلاعات مددکار" dir="rtl">
      <header className="fh-intake__heading">
        <div>
          <span className="fh-intake__eyebrow">دموی محیط مددکار · پرونده HM-1405-021</span>
          <h1>ثبت خط مبنای مدل هامون</h1>
          <p>ثبت مشاهده بر اساس ابعاد PGOR، همراه با منبع و زمان اثر.</p>
        </div>
        <span className="fh-intake__badge">نمونهٔ ساختگی</span>
      </header>

      <div className="fh-intake__notice" role="note">
        <strong>دموی بدون اتصال</strong>
        <span>اطلاعات واقعی وارد نکنید. داده‌ای به سرور نمی‌رود و با تازه‌سازی صفحه پاک می‌شود.</span>
      </div>

      <div className="fh-intake__grid">
        <section className="fh-intake__card">
          <div className="fh-intake__section-head">
            <div><small>ارزیابی پایه · PGOR</small><h2>ثبت مشاهدهٔ مدل</h2></div>
            <span className="fh-intake__step">گام ۱</span>
          </div>

          <div className="fh-intake__dimensions" aria-label="ابعاد مدل PGOR">
            {dimensions.map((item) => (
              <button
                key={item.code}
                type="button"
                className={dimension === item.code ? "fh-intake__dimension is-active" : "fh-intake__dimension"}
                aria-pressed={dimension === item.code}
                onClick={() => setDimension(item.code)}
              >
                <strong>{item.code}</strong><span>{item.name}</span>
              </button>
            ))}
          </div>

          <div className="fh-intake__model-note">
            <strong>نکته دربارهٔ تعریف مدل</strong>
            <span>در سامانهٔ متصل، شاخص‌ها و بازهٔ امتیاز از نسخهٔ فعال PGOR خوانده می‌شوند و ثبت برای هر شاخص انجام می‌شود. این دمو به آن تعریف وصل نیست؛ امتیاز اینجا فقط نمایشی است و محاسبهٔ رسمی نمی‌شود.</span>
          </div>

          <form onSubmit={submit} className="fh-intake__form">
            <label>
              امتیاز نمایشی بُعد {dimension}
              <input required type="number" min="0" max="100" step="0.01" value={score} onChange={(event) => setScore(event.target.value)} />
            </label>
            <label>
              منبع مشاهده
              <select required value={source} onChange={(event) => setSource(event.target.value)}>
                <option value="">منبع را انتخاب کنید</option>
                <option value="اظهار خانوار">اظهار خانوار</option>
                <option value="ارزیابی مددکار">ارزیابی مددکار</option>
                <option value="دادهٔ بیرونی">دادهٔ بیرونی</option>
              </select>
            </label>
            <label>
              زمان اثر اطلاعات
              <input required type="date" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} />
            </label>
            <button className="fh-intake__submit" type="submit">ثبت نمونه برای بازبینی <span aria-hidden="true">←</span></button>
          </form>
          {notice ? <p className="fh-intake__notice-text" role="status">{notice}</p> : null}
        </section>

        <aside className="fh-intake__card fh-intake__review">
          <div className="fh-intake__section-head">
            <div><small>کنترل کیفیت</small><h2>بازبینی انسانی</h2></div>
            <span className="fh-intake__review-icon" aria-hidden="true">✓</span>
          </div>
          <ol>
            <li><span>۱</span><div><strong>ثبت مشاهدهٔ شاخص</strong><small>طبق تعریف فعال PGOR</small></div></li>
            <li><span>۲</span><div><strong>اعتبارسنجی مستقل</strong><small>تأیید، اختلاف یا رد</small></div></li>
            <li><span>۳</span><div><strong>پذیرش صریح</strong><small>فقط پس از تصمیم انسانی</small></div></li>
          </ol>
          <p>در نسخهٔ واقعی، هر مشاهده به ارزیابی و نسخهٔ تعریف مدل متصل است. ثبت داده به‌تنهایی مدل را آموزش نمی‌دهد.</p>
        </aside>
      </div>

      <section className="fh-intake__card fh-intake__history">
        <div className="fh-intake__section-head">
          <div><small>رد ثبت‌های نمایشی</small><h2>در انتظار بازبینی</h2></div>
          <span className="fh-intake__count">{entries.length.toLocaleString("fa-IR")} مورد</span>
        </div>
        {entries.length === 0 ? (
          <div className="fh-intake__empty">برای دیدن وضعیت پس از ثبت، فرم نمونه را تکمیل کنید.</div>
        ) : (
          <div className="fh-intake__entries">
            {entries.map((entry) => (
              <article key={entry.id}>
                <div><strong>بُعد {entry.dimension} · امتیاز نمایشی {Number(entry.score).toLocaleString("fa-IR")}</strong><small>منبع: {entry.source} · زمان اثر: {entry.effectiveAt}</small></div>
                <span>در انتظار اعتبارسنجی</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
