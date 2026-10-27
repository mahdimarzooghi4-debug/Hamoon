import { useState, type FormEvent } from "react";
import "./figma-home-demo.css";

const metrics = [
  { icon: "▣", label: "خانوارهای فعال", hint: "در چرخه توانمندسازی", value: "۱٬۲۴۸" },
  { icon: "♧", label: "پرونده‌های نیازمند بررسی", hint: "۲ مورد جدید", value: "۳۳" },
  { icon: "◉", label: "مداخلات در حال اجرا", hint: "در ۸ برنامه فعال", value: "۱۲۶" },
  { icon: "▦", label: "پیگیری‌های امروز", hint: "۶ مورد با اولویت بالا", value: "۱۸" },
];

const shortcuts = [
  ["▱", "پرونده‌های من", "۱۲۸ مورد"],
  ["➤", "ارجاعات فعال", "۴۳ مورد"],
  ["▦", "پیگیری‌ها", "۱۸ امروز"],
  ["⊙", "موارد نیازمند تصمیم", "۳ مورد"],
  ["♧", "تیم توانمندسازی", "۸ واحد"],
];

const rows = [
  ["نمونه ۰۱", "۰۶۸", "توانمندسازی", "امروز، ۰۹:۳۰", "تأیید برنامه اشتغال", "↗"],
  ["نمونه ۰۲", "۰۵۱", "نیازمند تصمیم", "دیروز، ۱۶:۰۰", "بازبینی گلوگاه", "—"],
  ["نمونه ۰۳", "۰۷۴", "در حال اجرا", "۲ روز پیش", "تماس پیگیری", "↗"],
  ["نمونه ۰۴", "۰۴۳", "توانمندسازی", "۴ روز پیش", "ارزیابی توانمندی", "↘"],
];

function HamoonMark() {
  return <img className="fh-mark" src="/demo-assets/hamoon-mark.svg" alt="" />;
}

function EmpowermentModel() {
  return (
    <div className="fh-model">
      <div className="fh-model__heading"><strong>مدل مسیر توانمندسازی</strong><span>نمایش خنثی · آماده تحلیل خانوار</span></div>
      <div className="fh-threshold fh-threshold--top"><span>E ≈ 1.0</span></div>
      <div className="fh-threshold fh-threshold--mid"><span>E = 0.7</span></div>
      <img className="fh-cylinder" src="/demo-assets/pgor-cylinder.svg" alt="مدل شیشه‌ای توانمندسازی هامون" />     <div className="fh-model__stage fh-model__stage--one"><i/><b>استقلال پایدار</b><small>E ≈ 1.0</small></div>
      <div className="fh-model__stage fh-model__stage--two"><i/><b>آستانه توانمندی</b><small>E = 0.7</small></div>
      <div className="fh-model__stage fh-model__stage--three"><i/><b>توانمندسازی</b><small>مسیر حمایت و رشد</small></div>
      <div className="fh-model__stage fh-model__stage--four"><i/><b>وابستگی</b><small>نقطه آغاز مسیر</small></div>
      <div className="fh-pgor">{[["R","تاب‌آوری"],["O","فرصت"],["G","ظرفیت رشد"],["P","مشارکت"]].map(([letter,label]) => <span key={letter}><b>{letter}</b>{label}</span>)}</div>
    </div>
  );
}

export function FigmaHomeDemo() {
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  function showPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(query.trim() ? "این جست‌وجو در نسخه‌ی نمایشی به پرونده‌ای متصل نمی‌شود." : "برای این دمو از کدهای نمونه استفاده کنید؛ پرونده‌ی واقعی متصل نیست.");
  }
  return (
    <div className="fh-app" dir="rtl">
      <header className="fh-topbar">
        <div className="fh-topbar__inner">
          <div className="fh-user">
            <button className="fh-profile" type="button" aria-label="پروفایل نمایشی">
              <span className="fh-avatar">م</span><span className="fh-user__copy"><b>نام مددکار</b><small>مددکار پرونده</small></span><span className="fh-chevron">⌄</span>
            </button>
            <button className="fh-icon-button" aria-label="تنظیمات" type="button">⚙</button>
            <button className="fh-icon-button fh-bell" aria-label="اعلان‌ها" type="button">♧<i/></button>
          </div>
          <div className="fh-brand">
            <span><b>هامون</b><small>ماشین توانمندسازی هوشمند</small></span><HamoonMark />
          </div>
        </div>
      </header>
      <main className="fh-content">
        <section className="fh-hero">
          <EmpowermentModel />
          <div className="fh-search-panel">
            <div className="fh-ready"><i/> موتور هوشمند هامون آماده است</div>
            <div className="fh-intro"><h1>پرونده هوشمند توانمندسازی خانوار</h1><p>برای مشاهده وضعیت، تشخیص و مسیر توانمندسازی، کد ملی خانوار را وارد کنید.</p></div>
            <form className="fh-search-form" onSubmit={showPreview}>
              <input value={query} onChange={event => setQuery(event.target.value)} aria-label="کد ملی خانوار" placeholder="مثال: ۰۰۱۲۳۴۵۶۷۸"/>
              <button type="submit"><span>←</span> مشاهده پرونده</button>
            </form>
            <button className="fh-advanced" onClick={() => setMessage("جست‌وجوی پیشرفته در این نسخه فقط برای نمایش قاب محصول است.")} type="button">☷ جستجوی پیشرفته</button>
            <div className="fh-cycle">{["یادگیری","سنجش","اقدام","تجویز","تشخیص","درک"].map((name,index)=><span className={index===5?"is-current":""} key={name}>{name}<i/></span>)}</div>
          </div>
        </section>
        <section className="fh-metrics">{metrics.map(item=><article className="fh-metric" key={item.label}><span className="fh-metric__icon">{item.icon}</span><div className="fh-metric__copy"><b>{item.label}</b><small>{item.hint}</small></div><strong>{item.value}</strong></article>)}</section>
        <section className="fh-shortcuts" aria-label="دسترسی‌های سریع">{shortcuts.map(([icon,label,hint])=><button type="button" onClick={()=>setMessage("این میانبر در نسخه‌ی نمایشی فقط ظاهر صفحه را نشان می‌دهد.")} key={label}><span>{icon}</span><b>{label}</b><small>{hint}</small></button>)}</section>
        <section className="fh-bottom">
          <aside className="fh-vision">
            <div className="fh-vision__brand"><HamoonMark/><div><b>بینش هامون</b><small>موتور هوشمند توانمندسازی</small></div></div>
            <ul><li>پرونده نیازمند بازبینی مسیر توانمندسازی هستند.</li><li>۲ خانوار با نقاط مداخله در شاخص تاب‌آوری شناسایی شدند.</li></ul>
            <button type="button" onClick={()=>setMessage("بینش‌ها در این دمو نمونه هستند و به داده‌ی واقعی متصل نیستند.")}>مشاهده همه موارد <span>←</span><small>۳ مورد · اولویت متوسط</small></button>
            <div className="fh-confidence">اعتماد تحلیلی ۷۸٪ <span>بر پایه‌ی شاخص PGOR و روند ۹۰ روزه</span></div>
          </aside>
          <section className="fh-recent">
            <header><div><b>خانوارهای اخیر</b><small>آخرین پرونده‌های مشاهده‌شده در حال اقدام</small></div><button type="button" onClick={()=>setMessage("فهرست کامل خانوارها در نسخه‌ی نمایشی متصل نیست.")}>مشاهده همه ←</button></header>
            <div className="fh-table-wrap"><table><thead><tr><th>نام خانوار</th><th>کد پرونده</th><th>E Score</th><th>وضعیت فعلی</th><th>روند</th><th>آخرین بررسی</th><th>اقدام بعدی</th></tr></thead><tbody>{rows.map((row,index)=><tr key={row[0]}><td><b>{row[0]}</b></td><td><span className="fh-case-icon">♧</span><small>•••{index+1}۸−۰</small></td><td><b>{row[1]}</b></td><td><span className={"fh-status fh-status--"+index}>{row[2]}</span></td><td className={index===3?"fh-down":"fh-up"}>{row[5]}</td><td>{row[3]}</td><td><b>{row[4]}</b></td></tr>)}</tbody></table></div>
          </section>
        </section>
        <footer className="fh-demo-note"><span/>دموی نمایشی هامون · همه‌ی اعداد و پرونده‌ها فرضی‌اند و هیچ اطلاعاتی ذخیره یا ارسال نمی‌شود.</footer>
      </main>
      {message && <div className="fh-toast" role="status"><span>{message}</span><button type="button" onClick={()=>setMessage("")}>بستن</button></div>}
    </div>
  );
}
