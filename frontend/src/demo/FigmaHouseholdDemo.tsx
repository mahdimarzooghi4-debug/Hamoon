import { useState } from "react";
import "./figma-household-demo.css";

const dimensions = [
  { id: "P", name: "مشارکت", score: "0.68", tone: "teal" },
  { id: "G", name: "ظرفیت رشد", score: "0.61", tone: "blue" },
  { id: "O", name: "فرصت", score: "0.34", tone: "cyan" },
  { id: "R", name: "تاب‌آوری", score: "0.53", tone: "gold" },
];

export function FigmaHouseholdDemo() {
  const [tab, setTab] = useState("نمای کلی");
  const [notice, setNotice] = useState("");
  return (
    <main className="fh-household" dir="rtl" aria-label="پرونده هوشمند خانوار">
      <header className="fh-household__case">
        <div>
          <span className="fh-household__eyebrow">پروندهٔ نمایشی · وضعیت داده: معتبر</span>
          <h1>خانوار احمدی</h1>
          <p>سرپرست: مریم احمدی <span>·</span> اعضا: ۴ نفر <span>·</span> منطقه: منطقهٔ ۱۳</p>
        </div>
        <div className="fh-household__case-meta"><b>کد پرونده H-1405-21842</b><small>آخرین ارزیابی: ۱۴۰۵/۰۷/۱۲ · مددکار: نام مددکار</small><button type="button" onClick={() => setNotice("جست‌وجوی پرونده در این دموی نمایشی به دادهٔ واقعی متصل نیست.")}>تغییر خانوار</button></div>
      </header>

      <nav className="fh-household__tabs" aria-label="بخش‌های پرونده">
        {["نمای کلی", "داده‌های PGOR", "اقدام‌ها", "تاریخچه"].map((item) => <button className={tab === item ? "is-active" : ""} key={item} onClick={() => setTab(item)} type="button">{item}</button>)}
      </nav>

      <div className="fh-household__grid">
        <section className="fh-household__model">
          <div className="fh-household__model-title"><span>نمایش خنثی · بدون امتیاز رسمی</span><h2>مدل مسیر توانمندسازی</h2></div>
          <div className="fh-household__score">E = 0.54</div>
          <div className="fh-household__cylinder" aria-label="نمایش شماتیک مسیر خانوار">
            <span className="fh-household__threshold fh-household__threshold--one">E = 1.0 <small>استقلال پایدار</small></span>
            <span className="fh-household__threshold fh-household__threshold--two">E = 0.70 <small>آستانه توانمندی</small></span>
            <div className="fh-household__ring fh-household__ring--outer" />
            <div className="fh-household__ring fh-household__ring--middle" />
            <div className="fh-household__ring fh-household__ring--inner" />
            <span className="fh-household__stage">مسیر حمایت و رشد</span>
          </div>
          <div className="fh-household__dimensions">
            {dimensions.map((item) => <div className={`fh-household__dimension fh-household__dimension--${item.tone}`} key={item.id}><b>{item.id}</b><span>{item.name}</span><strong>{item.score}</strong></div>)}
          </div>
        </section>

        <div className="fh-household__right">
          <section className="fh-household__card fh-household__diagnosis">
            <div className="fh-household__card-head"><div><small>تشخیص اصلی · نسخهٔ نمایشی</small><h2>تشخیص هامون</h2></div><span className="fh-household__badge">سطح اطمینان: متوسط</span></div>
            <h3>محدودیت دسترسی خانوار به فرصت پایدار اشتغال</h3>
            <div className="fh-household__tags"><span>ناپایداری درآمد</span><span>شبکهٔ ارتباطی محدود</span><span>ظرفیت مهارتی قابل توسعه</span></div>
            <button className="fh-household__link" onClick={() => setNotice("توضیح تشخیص در این نسخه صرفاً نمایشی است.")} type="button">چرا هامون به این تشخیص رسیده؟ ←</button>
          </section>

          <section className="fh-household__card fh-household__decision">
            <div className="fh-household__card-head"><div><small>تصمیم مددکار</small><h2>بازبینی انسانی</h2></div><span className="fh-household__status">در انتظار بررسی</span></div>
            <p>تشخیص اصلی هامون در تاریخچهٔ پرونده ذخیره می‌ماند و تصمیم نهایی با مددکار است.</p>
            <div className="fh-household__buttons">
              <button onClick={() => setNotice("در دمو، تصمیم به سرور ارسال نمی‌شود.")} type="button">تأیید تشخیص</button>
              <button onClick={() => setNotice("فرم اصلاح تشخیص در این دمو ذخیره نمی‌شود.")} type="button">اصلاح تشخیص</button>
              <button className="is-quiet" onClick={() => setNotice("یادداشت نمایشی ثبت نشد.")} type="button">ثبت توضیح</button>
            </div>
          </section>

          <section className="fh-household__next">
            <div><small>اقدام بعدی مددکار</small><h2>پیگیری ارجاع اشتغال</h2><p>مهلت: ۳ روز آینده · نتیجهٔ ارجاع را با منبع معتبر مرور کنید.</p></div>
            <button onClick={() => setNotice("پیگیری نمونه در این دمو ذخیره یا ارسال نمی‌شود.")} type="button">ثبت پیگیری</button>
          </section>
        </div>
      </div>

      <section className="fh-household__card fh-household__history">
        <div className="fh-household__card-head"><div><small>{tab}</small><h2>{tab === "نمای کلی" ? "آخرین تغییرات پرونده" : tab}</h2></div><span className="fh-household__badge">۳ مورد اخیر</span></div>
        <div className="fh-household__history-list">
          <article><b>ارزیابی توانمندسازی</b><span>نسخهٔ نمایشی · ۱۴۰۵/۰۷/۱۲</span><small>مقادیر این پرونده برای نمایش رابط ساختگی‌اند.</small></article>
          <article><b>ارجاع خدمت اشتغال</b><span>در انتظار نتیجه · ۱۴۰۵/۰۷/۰۹</span><small>پیگیری انسانی لازم است.</small></article>
          <article><b>بازبینی تشخیص</b><span>نیازمند تصمیم · ۱۴۰۵/۰۷/۰۸</span><small>هامون به‌تنهایی تصمیم را ثبت نمی‌کند.</small></article>
        </div>
      </section>
      {notice ? <p className="fh-household__notice" role="status">{notice}</p> : null}
      <footer className="fh-household__footer">دموی نمایشی هامون · همهٔ اطلاعات و پرونده‌ها ساختگی‌اند؛ اطلاعات واقعی وارد نکنید.</footer>
    </main>
  );
}
