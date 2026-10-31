import { useState } from "react";
import "./figma-reassessment-demo.css";

const steps = ["اطلاعات جدید", "ارزیابی PGOR", "نتیجهٔ هامون", "تأیید مددکار"];
const changeGroups = [
  {
    title: "معیشت و مسکن",
    fields: [
      ["وضعیت اشتغال", "بیکار", "اکنون: شاغل پاره‌وقت", "ثبت تغییر"],
      ["درآمد ماهانه", "۱۳ میلیون تومان", "۱۸ میلیون تومان", "ثبت تغییر"],
      ["مسکن فعلی", "اجاره‌ای", "بدون تغییر", "بدون تغییر"],
    ],
  },
  {
    title: "ترکیب و شرایط خانوار",
    fields: [
      ["ترکیب خانوار", "۴ نفر", "بدون تغییر", "بدون تغییر"],
      ["سلامت / شرایط اثرگذار", "بیماری مزمن ندارد", "کاهش توان کاری سرپرست", "ثبت تغییر"],
      ["دسترسی به خدمات", "دسترسی محدود", "مرکز خدمات محله فعال شده", "ثبت تغییر"],
      ["رویداد مهم اخیر", "ثبت نشده", "شروع کار پاره‌وقت، ۱۸ مهر", "ثبت تغییر"],
    ],
  },
];

export function FigmaReassessmentDemo() {
  const [step, setStep] = useState(0);
  const [notice, setNotice] = useState("");
  return (
    <main className="fh-reassessment" dir="rtl" aria-label="شروع ارزیابی مجدد">
      <aside className="fh-reassessment__backdrop">
        <div className="fh-reassessment__backdrop-head"><small>نمای پروندهٔ پیشین</small><strong>خانوار احمدی</strong><span>E = 0.54</span></div>
        <div className="fh-reassessment__model"><i/><i/><i/><b>مسیر توانمندسازی</b></div>
        <div className="fh-reassessment__backdrop-foot"><span>فرصت · ۰٫۳۴</span><span>ارزیابی مجدد</span></div>
      </aside>
      <section className="fh-reassessment__panel">
        <header className="fh-reassessment__heading">
          <div><span className="fh-reassessment__eyebrow">۰۱ · شروع ارزیابی مجدد</span><h1>ارزیابی مجدد خانوار</h1><p>خانوار احمدی · کد پروندهٔ H-1405-21842</p></div>
          <button aria-label="بستن" onClick={() => setNotice("خروج از ارزیابی در این دموی نمایشی ذخیره نمی‌شود.")} type="button">×</button>
        </header>

        <nav className="fh-reassessment__steps" aria-label="گام‌های ارزیابی">
          {steps.map((item, index) => <button aria-current={step === index ? "step" : undefined} className={step === index ? "is-active" : index < step ? "is-complete" : ""} key={item} onClick={() => setStep(index)} type="button"><b>{index + 1}</b><span>{item}</span></button>)}
        </nav>

        <div className="fh-reassessment__intro"><span>آخرین ارزیابی: ۱۴۰۵/۰۷/۱۲ · مقدار فعلی E: ۰٫۵۴</span><h2>{step === 0 ? "چه چیزی از ارزیابی قبلی تغییر کرده است؟" : steps[step]}</h2><p>داده‌های قبلی محفوظ می‌مانند. فقط تغییرات را ثبت کنید؛ مقادیر تازه در این دمو به پرونده یا مدل ارسال نمی‌شوند.</p></div>

        {step === 0 ? <div className="fh-reassessment__groups">
          {changeGroups.map((group) => <section className="fh-reassessment__card" key={group.title}>
            <h3>{group.title}</h3>
            <div className="fh-reassessment__rows">{group.fields.map(([label, current, next, status]) => <article key={label}>
              <div className="fh-reassessment__current"><small>{label} · فعلی</small><b>{current}</b></div>
              <div className="fh-reassessment__next"><small>مشاهدهٔ جدید</small><b>{next}</b></div>
              <span className={status === "ثبت تغییر" ? "fh-reassessment__changed" : "fh-reassessment__unchanged"}>{status}</span>
            </article>)}</div>
          </section>)}
        </div> : <section className="fh-reassessment__card fh-reassessment__placeholder">
          <h3>{steps[step]}</h3><p>این گام برای نمایش مسیر ارزیابی آماده است؛ در این دمو محاسبه یا ارسال داده انجام نمی‌شود.</p>
        </section>}

        {notice ? <p className="fh-reassessment__notice" role="status">{notice}</p> : null}
        <footer className="fh-reassessment__actions"><button className="is-quiet" disabled={step === 0} onClick={() => setStep((current) => Math.max(0, current - 1))} type="button">بازگشت</button><span>گام {step + 1} از {steps.length}</span><button onClick={() => step < steps.length - 1 ? setStep((current) => current + 1) : setNotice("ارزیابی نمونه تکمیل نشد و هیچ داده‌ای ثبت نشد.")} type="button">{step === steps.length - 1 ? "پایان دمو" : "ادامه"}</button></footer>
      </section>
    </main>
  );
}
