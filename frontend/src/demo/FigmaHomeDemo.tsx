import { useState, type FormEvent } from "react";
import "./figma-home-demo.css";

const metrics = [
  { icon: "calendar-check", label: "خانوارهای فعال", hint: "در چرخه توانمندسازی", value: "۱٬۲۴۸" },
  { icon: "file-search", label: "پرونده‌های نیازمند بررسی", hint: "۳ مورد جدید", value: "۲۳" },
  { icon: "activity", label: "مداخلات در حال اجرا", hint: "در ۸ برنامه فعال", value: "۱۲۶" },
  { icon: "calendar-clock", label: "پیگیری‌های امروز", hint: "۶ مورد با اولویت بالا", value: "۱۸" },
];

const shortcuts = [
  ["folder", "پرونده‌های من", "۸۶ پرونده"],
  ["send", "ارجاعات فعال", "۳۴ فعال"],
  ["calendar-clock", "پیگیری‌ها", "۱۸ امروز"],
  ["circle-check", "موارد نیازمند تصمیم", "۹ مورد"],
  ["file-search", "نتایج جدید ارائه‌دهندگان", "۵ جدید"],
];

type TrendDirection = "up" | "flat" | "down";
type HouseholdRow = [string, string, string, string, string, TrendDirection, string];

const rows: HouseholdRow[] = [
  ["خانوار احمدی", "۰٫۶۸", "توانمندسازی", "امروز، ۰۹:۴۵", "تأیید برنامه اشتغال", "up", "هـ-۴۱۲۸"],
  ["خانوار رضایی", "۰٫۵۱", "نیازمند تصمیم", "دیروز، ۱۶:۲۰", "بازبینی گلوگاه", "flat", "هـ-۳۹۸۲"],
  ["خانوار محمدی", "۰٫۷۴", "پیگیری فعال", "۲ روز پیش", "تماس پیگیری", "up", "هـ-۳۷۵۴"],
  ["خانوار کریمی", "۰٫۴۳", "توانمندسازی", "۳ روز پیش", "ارزیابی تاب‌آوری", "down", "هـ-۳۶۱۱"],
];

type UiIconName = "settings" | "bell" | "calendar-check" | "file-search" | "activity" | "calendar-clock" | "folder" | "send" | "circle-check" | "users" | "search" | "sliders";

function UiIcon({ name }: { name: UiIconName }) {
  const common = { stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg className="fh-ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...common}>
      {name === "settings" ? <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.7 2.94-.08-.03a1.7 1.7 0 0 0-1.82.2l-.08.06h-3.4l-.02-.09a1.7 1.7 0 0 0-1.35-1.36l-.09-.02-1.7-2.94.06-.07A1.7 1.7 0 0 0 9.96 14l-.03-.1v-3.4l.09-.02a1.7 1.7 0 0 0 1.36-1.35l.02-.09h3.4l.08.06a1.7 1.7 0 0 0 1.82.2l.08-.03 1.7 2.94-.06.06A1.7 1.7 0 0 0 19.4 15Z"/></> :
      name === "bell" ? <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></> :
      name === "calendar-check" ? <><rect x="3.5" y="5" width="17" height="16" rx="2.5"/><path d="M8 3v4M16 3v4M3.5 9.5h17M8 15l2.4 2.2 5-5"/></> :
      name === "file-search" ? <><path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7"/><path d="M13 3v5h5M13 3l5 5"/><circle cx="16.5" cy="16" r="3"/><path d="m18.7 18.2 2 2"/></> :
      name === "activity" ? <><path d="M3 12h4l2.5-7 4.5 14 2.5-7H21"/></> :
      name === "calendar-clock" ? <><rect x="3.5" y="5" width="17" height="16" rx="2.5"/><path d="M8 3v4M16 3v4M3.5 9.5h17"/><circle cx="12" cy="15" r="3"/><path d="M12 13.5V15l1 1"/></> :
      name === "folder" ? <><path d="M3 6.5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></> :
      name === "send" ? <><path d="m21 3-7.2 18-3.6-7.2L3 10.2 21 3Z"/><path d="M10.2 13.8 15 9"/></> :
      name === "circle-check" ? <><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></> :
      name === "users" ? <><path d="M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20"/><circle cx="9.5" cy="7.5" r="3.5"/><path d="M17 11a3.5 3.5 0 1 0-1-6.8M17 14h1a4 4 0 0 1 4 4v2"/></> :
      name === "search" ? <><circle cx="10.8" cy="10.8" r="6.3"/><path d="m16 16 4.2 4.2"/></> :
      <><path d="M4 7h16M7 12h10M10 17h4"/><circle cx="8" cy="7" r="1.2" fill="currentColor"/><circle cx="15" cy="12" r="1.2" fill="currentColor"/></>}
    </svg>
  );
}

function TrendIcon({ direction }: { direction: TrendDirection }) {
  const label = direction === "up" ? "روند صعودی" : direction === "down" ? "روند نزولی" : "روند ثابت";
  return (
    <svg className={`fh-trend fh-trend--${direction}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" role="img" aria-label={label}>
      {direction === "up" ? <><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></> :
       direction === "down" ? <><path d="M3 7l6 6 4-4 8 8"/><path d="M14 17h7v-7"/></> :
       <path d="M5 12h14"/>}
    </svg>
  );
}

function HamoonMark() {
  return <img className="fh-mark" src="/demo-assets/hamoon-mark.svg" alt="" />;
}
function VisionMark() {
  return <img className="fh-mark fh-mark--vision" src="/demo-assets/hamoon-mark.svg" alt="" />;
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
            <button className="fh-icon-button" aria-label="تنظیمات" type="button"><UiIcon name="settings"/></button>
            <button className="fh-icon-button fh-bell" aria-label="اعلان‌ها" type="button"><UiIcon name="bell"/><i/></button>
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
              <label className="fh-input-wrap"><span><b>کد ملی خانوار</b><input value={query} onChange={event => setQuery(event.target.value)} aria-label="کد ملی خانوار" placeholder="مثال: ۰۰۱۲۳۴۵۶۷۸"/></span><UiIcon name="search"/></label>
              <button type="submit"><span>←</span> مشاهده پرونده</button>
            </form>
            <button className="fh-advanced" onClick={() => setMessage("جست‌وجوی پیشرفته در این نسخه فقط برای نمایش قاب محصول است.")} type="button"><UiIcon name="sliders"/> جستجوی پیشرفته</button>
            <div className="fh-cycle">{["یادگیری","سنجش","اقدام","تجویز","تشخیص","درک"].map((name,index)=><span className={index===5?"is-current":""} key={name}>{name}<i/></span>)}</div>
          </div>
        </section>
        <section className="fh-metrics">{metrics.map(item=><article className="fh-metric" key={item.label}><span className="fh-metric__icon"><UiIcon name={item.icon as UiIconName}/></span><div className="fh-metric__copy"><b>{item.label}</b><small>{item.hint}</small></div><strong>{item.value}</strong></article>)}</section>
        <section className="fh-shortcuts" aria-label="دسترسی‌های سریع">{shortcuts.map(([icon,label,hint])=><button type="button" onClick={()=>setMessage("این میانبر در نسخه‌ی نمایشی فقط ظاهر صفحه را نشان می‌دهد.")} key={label}><UiIcon name={icon as UiIconName}/><b>{label}</b><small>{hint}</small></button>)}</section>
        <section className="fh-bottom">
          <aside className="fh-vision">
            <div className="fh-vision__head"><span className="fh-vision__time">◷ ۸ دقیقه پیش</span><div className="fh-vision__brand"><VisionMark/><div><b>بینش هامون</b><small>لایه هوشمند تصمیم‌یار</small></div></div></div>
            <ul><li>۳ پرونده نیازمند بازبینی مسیر توانمندسازی هستند.</li><li>۲ خانوار افت معنادار در شاخص تاب‌آوری داشته‌اند.</li></ul>
            <button type="button" onClick={()=>setMessage("این بینش‌ها در نسخه‌ی نمایشی فقط برای نمایش قاب هستند.")}>مشاهده موارد <span>←</span><small>مرتب‌شده بر اساس اولویت تصمیم</small></button>
            <div className="fh-confidence">اعتماد تحلیل ۸۷٪ <span>بر پایه تغییرات PGOR و روند E</span></div>
          </aside>
          <section className="fh-recent">
            <header><div><b>خانوارهای اخیر</b><small>آخرین پرونده‌های مشاهده‌شده و در حال اقدام</small></div><button type="button" onClick={()=>setMessage("فهرست کامل خانوارها در نسخه‌ی نمایشی متصل نیست.")}>مشاهده همه ←</button></header>
            <div className="fh-table-wrap"><table><thead><tr><th>نام خانوار</th><th>کد پرونده</th><th>E Score</th><th>وضعیت فعلی</th><th>روند</th><th>آخرین بررسی</th><th>اقدام بعدی</th></tr></thead><tbody>{rows.map((row,index)=><tr key={row[0]}><td><b>{row[0]}</b></td><td><span className="fh-case-icon"><UiIcon name="users"/></span><small>{row[6]}</small></td><td><b>{row[1]}</b></td><td><span className={"fh-status fh-status--"+index}>{row[2]}</span></td><td className="fh-trend-cell"><TrendIcon direction={row[5]} /></td><td>{row[3]}</td><td><b>{row[4]}</b></td></tr>)}</tbody></table></div>
          </section>
        </section>
        <footer className="fh-demo-note"><span/>دموی نمایشی هامون · همه‌ی اعداد و پرونده‌ها فرضی‌اند و هیچ اطلاعاتی ذخیره یا ارسال نمی‌شود.</footer>
      </main>
      {message && <div className="fh-toast" role="status"><span>{message}</span><button type="button" onClick={()=>setMessage("")}>بستن</button></div>}
    </div>
  );
}
