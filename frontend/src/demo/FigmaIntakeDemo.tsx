import { useState, type FormEvent } from "react";

type DimensionCode = "P" | "G" | "O" | "R";
type PromptItem = { id: string; title: string; context: string };
type DemoAnswer = {
  id: number;
  dimension: DimensionCode;
  indicator: string;
  answer: string;
  source: string;
  effectiveAt: string;
};

const dimensions: {
  code: DimensionCode;
  name: string;
  summary: string;
  items: PromptItem[];
}[] = [
  {
    code: "P",
    name: "مشارکت",
    summary: "میزان درگیری فعال خانوار در فرایند تغییر",
    items: [
      { id: "motivation", title: "انگیزه", context: "تمایل به تغییر و امید به آینده" },
      { id: "responsibility", title: "مسئولیت‌پذیری", context: "پیگیری امور و انجام تعهدات" },
      { id: "interaction", title: "تعامل", context: "ارتباط با نهادها و مشارکت اجتماعی" },
      { id: "programs", title: "حضور در برنامه‌ها", context: "آموزش، جلسات و فعالیت‌های توسعه‌ای" },
    ],
  },
  {
    code: "G",
    name: "ظرفیت رشد",
    summary: "توان بالقوه خانوار برای پیشرفت",
    items: [
      { id: "human-capital", title: "سرمایه انسانی", context: "تحصیلات و مهارت" },
      { id: "experience", title: "تجربه", context: "سابقه کاری و تجربه تولید" },
      { id: "learning", title: "قابلیت یادگیری", context: "آموزش‌پذیری و انعطاف" },
      { id: "functional-health", title: "سلامت عملکردی", context: "توان جسمی و توان شناختی" },
    ],
  },
  {
    code: "O",
    name: "فرصت",
    summary: "دسترسی خانوار به بسترهای واقعی رشد",
    items: [
      { id: "market", title: "بازار", context: "تقاضا و اشتغال" },
      { id: "infrastructure", title: "زیرساخت", context: "حمل‌ونقل و اینترنت" },
      { id: "access", title: "دسترسی", context: "خدمات و سرمایه" },
      { id: "network", title: "شبکه اقتصادی", context: "ارتباطات و زنجیره ارزش" },
    ],
  },
  {
    code: "R",
    name: "تاب‌آوری",
    summary: "توان مقاومت خانوار در برابر شوک‌ها",
    items: [
      { id: "income-stability", title: "ثبات درآمد", context: "" },
      { id: "social-support", title: "حمایت اجتماعی", context: "" },
      { id: "family-health", title: "سلامت خانوادگی", context: "" },
      { id: "crisis-response", title: "توان مقابله با بحران", context: "" },
      { id: "income-diversity", title: "تنوع منابع درآمدی", context: "" },
    ],
  },
];

const responseOptions = ["خیلی کم", "کم", "متوسط", "بالا", "خیلی بالا"];

export function FigmaIntakeDemo() {
  const [dimension, setDimension] = useState<DimensionCode>("P");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [source, setSource] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [entries, setEntries] = useState<DemoAnswer[]>([]);
  const [notice, setNotice] = useState("");

  const activeDimension = dimensions.find((item) => item.code === dimension)!;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!source || !effectiveAt) return;
    const completed = activeDimension.items.flatMap((item) => {
      const answer = answers[item.id];
      return answer ? [{
        id: Date.now() + activeDimension.items.indexOf(item),
        dimension,
        indicator: item.title,
        answer,
        source,
        effectiveAt,
      }] : [];
    });
    if (completed.length === 0) {
      setNotice("برای ثبت نمونه، دست‌کم یک پاسخ را انتخاب کنید.");
      return;
    }
    setEntries((current) => [...completed.reverse(), ...current]);
    setAnswers({});
    setSource("");
    setEffectiveAt("");
    setNotice("پاسخ‌های نمونه فقط در حافظه این صفحه ثبت شدند؛ با بستن یا تازه‌سازی صفحه پاک می‌شوند.");
  }

  return (
    <main className="fh-intake" aria-label="دموی پرسشنامه مددکار" dir="rtl">
      <header className="fh-intake__heading">
        <div>
          <span className="fh-intake__eyebrow">دموی محیط مددکار · پرونده HM-1405-021</span>
          <h1>تکمیل میدانی اطلاعات خانوار</h1>
          <p>پاسخ‌ها زیر دسته‌های مدل PGOR ثبت می‌شوند؛ مددکار امتیاز نهایی مدل را وارد نمی‌کند.</p>
        </div>
        <span className="fh-intake__badge">نمونهٔ ساختگی</span>
      </header>

      <div className="fh-intake__notice" role="note">
        <strong>دموی بدون اتصال</strong>
        <span>اطلاعات واقعی وارد نکنید. پاسخ‌ها به سرور نمی‌روند و با تازه‌سازی صفحه پاک می‌شوند.</span>
      </div>

      <div className="fh-intake__grid">
        <section className="fh-intake__card">
          <div className="fh-intake__section-head">
            <div><small>داده‌های سنجش توانمندسازی</small><h2>ثبت پاسخ بر اساس دستهٔ PGOR</h2></div>
            <span className="fh-intake__step">گام ۲</span>
          </div>

          <div className="fh-intake__dimensions" role="tablist" aria-label="دسته‌های PGOR">
            {dimensions.map((item) => (
              <button
                key={item.code}
                type="button"
                role="tab"
                aria-selected={dimension === item.code}
                className={dimension === item.code ? "fh-intake__dimension is-active" : "fh-intake__dimension"}
                onClick={() => { setDimension(item.code); setNotice(""); }}
              >
                <strong>{item.code}</strong><span>{item.name}</span>
              </button>
            ))}
          </div>

          <div className="fh-intake__model-note">
            <strong>{activeDimension.code} — {activeDimension.name}</strong>
            <span>{activeDimension.summary}</span>
            <span>نمونهٔ دسته‌ها و شاخص‌ها از فریم تکمیل میدانی فیگما آمده‌اند؛ فهرست کامل و انواع پاسخ باید از تعریف تأییدشدهٔ مدل بارگذاری شوند.</span>
          </div>

          <form onSubmit={submit} className="fh-intake__form">
            <div className="fh-intake__questions">
              {activeDimension.items.map((item) => (
                <fieldset className="fh-intake__question" key={item.id}>
                  <legend><strong>{item.title}</strong>{item.context ? <small>{item.context}</small> : null}</legend>
                  <div className="fh-intake__answers" role="group" aria-label={`پاسخ برای ${item.title}`}>
                    {responseOptions.map((option) => (
                      <label className={answers[item.id] === option ? "fh-intake__answer is-selected" : "fh-intake__answer"} key={option}>
                        <input
                          type="radio"
                          name={item.id}
                          value={option}
                          checked={answers[item.id] === option}
                          onChange={() => setAnswers((current) => ({ ...current, [item.id]: option }))}
                        />
                        <span>{option}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
            <div className="fh-intake__source-row">
              <label>
                منبع اصلی داده
                <select required value={source} onChange={(event) => setSource(event.target.value)}>
                  <option value="">منبع را انتخاب کنید</option>
                  <option value="خوداظهاری خانوار">خوداظهاری خانوار</option>
                  <option value="ارزیابی کارشناسی">ارزیابی کارشناسی</option>
                  <option value="داده‌های بیرونی">داده‌های بیرونی</option>
                </select>
              </label>
              <label>
                تاریخ اثر
                <input required type="date" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} />
              </label>
            </div>
            <button className="fh-intake__submit" type="submit">ثبت پاسخ‌های نمونه برای بازبینی <span aria-hidden="true">←</span></button>
          </form>
          {notice ? <p className="fh-intake__notice-text" role="status">{notice}</p> : null}
        </section>

        <aside className="fh-intake__card fh-intake__review">
          <div className="fh-intake__section-head">
            <div><small>روند ثبت</small><h2>ثبت و بازبینی انسانی</h2></div>
            <span className="fh-intake__review-icon" aria-hidden="true">✓</span>
          </div>
          <ol>
            <li><span>۱</span><div><strong>پرسش‌های دسته‌بندی‌شده</strong><small>پاسخ بر اساس شاخص PGOR</small></div></li>
            <li><span>۲</span><div><strong>ثبت منبع و تاریخ اثر</strong><small>هر مقدار با منشأ مستقل</small></div></li>
            <li><span>۳</span><div><strong>مرور و تصمیم انسانی</strong><small>تعارض‌ها حفظ و بررسی می‌شوند</small></div></li>
          </ol>
          <p>قرارداد فعلی سرور برای مشاهدهٔ PGOR عدد ۰ تا ۱۰۰ می‌گیرد و پاسخ‌نامهٔ دسته‌بندی‌شده را ذخیره نمی‌کند. این نمونه هیچ پاسخی را به امتیاز تبدیل نمی‌کند.</p>
        </aside>
      </div>

      <section className="fh-intake__card fh-intake__history">
        <div className="fh-intake__section-head">
          <div><small>رد ثبت‌های نمایشی</small><h2>پاسخ‌های در انتظار بازبینی</h2></div>
          <span className="fh-intake__count">{entries.length.toLocaleString("fa-IR")} پاسخ</span>
        </div>
        {entries.length === 0 ? (
          <div className="fh-intake__empty">پاسخ‌های انتخاب‌شده پس از ثبت نمونه در این بخش نمایش داده می‌شوند.</div>
        ) : (
          <div className="fh-intake__entries">
            {entries.map((entry) => (
              <article key={entry.id}>
                <div><strong>{entry.dimension} · {entry.indicator}: {entry.answer}</strong><small>منبع: {entry.source} · تاریخ اثر: {entry.effectiveAt}</small></div>
                <span>در انتظار اعتبارسنجی</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
