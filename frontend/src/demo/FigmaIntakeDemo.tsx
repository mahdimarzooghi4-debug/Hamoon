import { useState, type FormEvent } from "react";

type DemoEntry = {
  id: number;
  employment: string;
  source: string;
  effectiveAt: string;
};

const employmentLabels: Record<string, string> = {
  EMPLOYED: "حداقل یک عضو خانوار شاغل است",
  UNEMPLOYED: "هیچ‌یک از اعضای خانوار شاغل نیستند",
};

export function FigmaIntakeDemo() {
  const [employment, setEmployment] = useState("");
  const [source, setSource] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [entries, setEntries] = useState<DemoEntry[]>([]);
  const [notice, setNotice] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!employment || !source || !effectiveAt) return;
    setEntries((current) => [
      { id: Date.now(), employment, source, effectiveAt },
      ...current,
    ]);
    setEmployment("");
    setSource("");
    setEffectiveAt("");
    setNotice("نمونه فقط در حافظه این صفحه ثبت شد؛ با بستن یا تازه‌سازی صفحه پاک می‌شود.");
  }

  return (
    <main className="fh-intake" aria-label="دموی ثبت اطلاعات مددکار" dir="rtl">
      <header className="fh-intake__heading">
        <div>
          <span className="fh-intake__eyebrow">دموی محیط مددکار · پرونده HM-1405-021</span>
          <h1>ثبت اطلاعات خانوار</h1>
          <p>اطلاعات واقعی ثبت نکنید. این صفحه فقط برای نمایش جریان ورود و بازبینی است.</p>
        </div>
        <span className="fh-intake__badge">نمونهٔ ساختگی</span>
      </header>

      <div className="fh-intake__notice" role="note">
        <strong>دموی بدون اتصال</strong>
        <span>چیزی به سرور یا پایگاه‌داده ارسال نمی‌شود؛ موارد ثبت‌شده با تازه‌سازی صفحه پاک می‌شوند.</span>
      </div>

      <div className="fh-intake__grid">
        <section className="fh-intake__card">
          <div className="fh-intake__section-head">
            <div><small>ثبت اولیه</small><h2>وضعیت اشتغال خانوار</h2></div>
            <span className="fh-intake__step">گام ۱</span>
          </div>
          <form onSubmit={submit} className="fh-intake__form">
            <label>
              وضعیت اشتغال
              <select required value={employment} onChange={(event) => setEmployment(event.target.value)}>
                <option value="">انتخاب کنید</option>
                <option value="EMPLOYED">{employmentLabels.EMPLOYED}</option>
                <option value="UNEMPLOYED">{employmentLabels.UNEMPLOYED}</option>
              </select>
            </label>
            <label>
              منبع اطلاعات
              <select required value={source} onChange={(event) => setSource(event.target.value)}>
                <option value="">منبع را انتخاب کنید</option>
                <option value="اظهار خانوار">اظهار خانوار</option>
                <option value="مشاهده مددکار">مشاهده مددکار</option>
                <option value="مدرک معتبر">مدرک معتبر</option>
              </select>
            </label>
            <label>
              زمان اثر اطلاعات
              <input required type="date" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} />
            </label>
            <button className="fh-intake__submit" type="submit">ثبت برای بازبینی <span aria-hidden="true">←</span></button>
          </form>
          {notice ? <p className="fh-intake__notice-text" role="status">{notice}</p> : null}
        </section>

        <aside className="fh-intake__card fh-intake__review">
          <div className="fh-intake__section-head">
            <div><small>کنترل کیفیت</small><h2>بازبینی انسانی</h2></div>
            <span className="fh-intake__review-icon" aria-hidden="true">✓</span>
          </div>
          <ol>
            <li><span>۱</span><div><strong>ثبت توسط مددکار</strong><small>مقدار، منبع و زمان اثر</small></div></li>
            <li><span>۲</span><div><strong>اعتبارسنجی مستقل</strong><small>تأیید، اختلاف یا رد</small></div></li>
            <li><span>۳</span><div><strong>پذیرش صریح</strong><small>فقط پس از تصمیم انسانی</small></div></li>
          </ol>
          <p>ورود اطلاعات به این دمو هیچ داده‌ای را برای آموزش مدل آماده یا ارسال نمی‌کند.</p>
        </aside>
      </div>

      <section className="fh-intake__card fh-intake__history">
        <div className="fh-intake__section-head">
          <div><small>رد ثبت‌ها</small><h2>اطلاعات در انتظار بازبینی</h2></div>
          <span className="fh-intake__count">{entries.length.toLocaleString("fa-IR")} مورد</span>
        </div>
        {entries.length === 0 ? (
          <div className="fh-intake__empty">برای دیدن وضعیت پس از ثبت، فرم نمونه را تکمیل کنید.</div>
        ) : (
          <div className="fh-intake__entries">
            {entries.map((entry) => (
              <article key={entry.id}>
                <div><strong>{employmentLabels[entry.employment]}</strong><small>منبع: {entry.source} · زمان اثر: {entry.effectiveAt}</small></div>
                <span>در انتظار اعتبارسنجی</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
