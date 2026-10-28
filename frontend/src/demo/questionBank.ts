export type Group = "P" | "G" | "O" | "R";
export type DemoIndicator = {
  id: string;
  group: Group;
  groupName: string;
  category: string;
  guidance: string;
  measurementMethod: string;
  score0Anchor: string;
  score50Anchor: string;
  score100Anchor: string;
  analysisUnitRule: "UNRESOLVED" | "MEMBER" | "HOUSEHOLD" | "AREA";
  evidenceSources: string[];
  evidencePeriodGuidance: string;
  householdAggregationGuidance: string;
  active: boolean;
  draft: boolean;
  revision: number;
};

export const groups: { id: Group; name: string }[] = [
  { id: "P", name: "مشارکت" },
  { id: "G", name: "ظرفیت رشد" },
  { id: "O", name: "فرصت" },
  { id: "R", name: "تاب‌آوری" },
];

export const storageKey = "hamoon-demo-pgor-indicators-v2";

const seeds: Omit<DemoIndicator, "active" | "draft" | "revision" | "measurementMethod" | "score0Anchor" | "score50Anchor" | "score100Anchor" | "analysisUnitRule" | "evidenceSources" | "evidencePeriodGuidance" | "householdAggregationGuidance">[] = [
  { id: "p-change", group: "P", groupName: "مشارکت", category: "تمایل به تغییر", guidance: "شواهد مربوط به تمایل خانوار برای پیگیری تغییرات مورد توافق را ثبت کنید." },
  { id: "p-hope", group: "P", groupName: "مشارکت", category: "امید به آینده", guidance: "شواهد مرتبط با برنامه‌ریزی خانوار برای آینده را ثبت کنید." },
  { id: "p-followup", group: "P", groupName: "مشارکت", category: "پیگیری امور", guidance: "پیگیری امور و اقدام‌های مورد توافق را بر اساس سوابق ثبت کنید." },
  { id: "p-commitment", group: "P", groupName: "مشارکت", category: "انجام تعهدات", guidance: "انجام تعهدهای ثبت‌شده را بر اساس شواهد موجود بسنجید." },
  { id: "p-institutions", group: "P", groupName: "مشارکت", category: "ارتباط با نهادها", guidance: "دسترسی و ارتباط ثبت‌شده با نهادهای مرتبط را ارزیابی کنید." },
  { id: "p-social", group: "P", groupName: "مشارکت", category: "مشارکت اجتماعی", guidance: "مشارکت اجتماعی مستندشده را ثبت کنید." },
  { id: "p-training", group: "P", groupName: "مشارکت", category: "حضور در آموزش", guidance: "حضور در دوره‌ها و فعالیت‌های آموزشی ثبت‌شده را ارزیابی کنید." },
  { id: "p-meetings", group: "P", groupName: "مشارکت", category: "حضور در جلسات", guidance: "حضور در جلسات مرتبط ثبت‌شده را ارزیابی کنید." },
  { id: "p-development", group: "P", groupName: "مشارکت", category: "فعالیت‌های توسعه‌ای", guidance: "مشارکت در فعالیت‌های توسعه‌ای ثبت‌شده را ارزیابی کنید." },

  { id: "g-education", group: "G", groupName: "ظرفیت رشد", category: "تحصیلات", guidance: "سطح تحصیلات اعضای خانوار را بر اساس منبع معتبر ثبت کنید." },
  { id: "g-skills", group: "G", groupName: "ظرفیت رشد", category: "مهارت", guidance: "مهارت‌های قابل استفاده اعضای خانوار را بر اساس شواهد ثبت کنید." },
  { id: "g-work", group: "G", groupName: "ظرفیت رشد", category: "سابقه کاری", guidance: "سابقه کاری ثبت‌شده اعضای خانوار را ارزیابی کنید." },
  { id: "g-production", group: "G", groupName: "ظرفیت رشد", category: "تجربه تولید", guidance: "تجربهٔ تولید یا عرضهٔ محصول و خدمت را بر اساس سوابق ثبت کنید." },
  { id: "g-learning", group: "G", groupName: "ظرفیت رشد", category: "آموزش‌پذیری", guidance: "شواهد موجود دربارهٔ مشارکت در یادگیری و آموزش را ثبت کنید." },
  { id: "g-flexibility", group: "G", groupName: "ظرفیت رشد", category: "انعطاف‌پذیری", guidance: "شواهد موجود دربارهٔ سازگاری با تغییر شرایط را ثبت کنید." },
  { id: "g-physical", group: "G", groupName: "ظرفیت رشد", category: "توان جسمی", guidance: "اطلاعات عملکردی مرتبط را فقط از منبع مجاز و با رعایت حریم خصوصی ثبت کنید." },
  { id: "g-cognitive", group: "G", groupName: "ظرفیت رشد", category: "توان شناختی", guidance: "اطلاعات عملکردی مرتبط را فقط از منبع مجاز و با رعایت حریم خصوصی ثبت کنید." },

  { id: "o-demand", group: "O", groupName: "فرصت", category: "تقاضای بازار", guidance: "تقاضای مستند برای کالا یا خدمات قابل ارائه در منطقه را ارزیابی کنید." },
  { id: "o-jobs", group: "O", groupName: "فرصت", category: "فرصت اشتغال", guidance: "فرصت‌های اشتغال قابل دسترس را بر اساس داده‌های موجود ثبت کنید." },
  { id: "o-transport", group: "O", groupName: "فرصت", category: "حمل‌ونقل", guidance: "دسترسی مؤثر به حمل‌ونقل موردنیاز برای کار و خدمات را ثبت کنید." },
  { id: "o-internet", group: "O", groupName: "فرصت", category: "اینترنت", guidance: "دسترسی پایدار به اینترنت موردنیاز برای کار یا آموزش را ثبت کنید." },
  { id: "o-services", group: "O", groupName: "فرصت", category: "دسترسی به خدمات", guidance: "دسترسی به خدمات موردنیاز و موانع ثبت‌شده را ارزیابی کنید." },
  { id: "o-capital", group: "O", groupName: "فرصت", category: "دسترسی به سرمایه", guidance: "دسترسی مستند به منابع سرمایه‌ای یا حمایتی را ثبت کنید." },
  { id: "o-connections", group: "O", groupName: "فرصت", category: "ارتباطات اقتصادی", guidance: "ارتباطات اقتصادی قابل استفاده و مستند را ارزیابی کنید." },
  { id: "o-value-chain", group: "O", groupName: "فرصت", category: "زنجیره ارزش", guidance: "دسترسی به حلقه‌های مرتبط زنجیره ارزش را بر اساس داده‌های موجود ثبت کنید." },

  { id: "r-income", group: "R", groupName: "تاب‌آوری", category: "ثبات درآمد", guidance: "ثبات و قابلیت پیش‌بینی منابع درآمدی را از داده‌های در دسترس ارزیابی کنید." },
  { id: "r-support", group: "R", groupName: "تاب‌آوری", category: "حمایت اجتماعی", guidance: "منابع حمایت اجتماعیِ قابل دسترس و مستند را ثبت کنید." },
  { id: "r-health", group: "R", groupName: "تاب‌آوری", category: "سلامت خانوادگی", guidance: "دادهٔ سلامت را فقط با منبع مجاز و رعایت حریم خصوصی ثبت کنید." },
  { id: "r-crisis", group: "R", groupName: "تاب‌آوری", category: "توان مقابله با بحران", guidance: "شواهد مربوط به دسترسی و توان خانوار برای مواجهه با بحران را ثبت کنید." },
  { id: "r-diversity", group: "R", groupName: "تاب‌آوری", category: "تنوع منابع درآمدی", guidance: "تعداد و تنوع منابع درآمدی ثبت‌شده را ارزیابی کنید." },
];

const initialIndicators: DemoIndicator[] = seeds.map((item) => ({
  ...item,
  active: true,
  measurementMethod: "",
  score0Anchor: "",
  score50Anchor: "",
  score100Anchor: "",
  analysisUnitRule: "UNRESOLVED",
  evidenceSources: [],
  evidencePeriodGuidance: "",
  householdAggregationGuidance: "",
  draft: true,
  revision: 1,
}));

export function loadDemoIndicators(): DemoIndicator[] {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.map((value, index) => {
        const item = value as Partial<DemoIndicator>;
        return {
          ...item,
          measurementMethod: typeof item.measurementMethod === "string" ? item.measurementMethod : "",
          score0Anchor: typeof item.score0Anchor === "string" ? item.score0Anchor : "",
          score50Anchor: typeof item.score50Anchor === "string" ? item.score50Anchor : "",
          score100Anchor: typeof item.score100Anchor === "string" ? item.score100Anchor : "",
          analysisUnitRule: item.analysisUnitRule === "MEMBER" || item.analysisUnitRule === "HOUSEHOLD" || item.analysisUnitRule === "AREA" ? item.analysisUnitRule : "UNRESOLVED",
          evidenceSources: Array.isArray(item.evidenceSources) ? item.evidenceSources.filter((source): source is string => typeof source === "string") : [],
          evidencePeriodGuidance: typeof item.evidencePeriodGuidance === "string" ? item.evidencePeriodGuidance : "",
          householdAggregationGuidance: typeof item.householdAggregationGuidance === "string" ? item.householdAggregationGuidance : "",
          revision: Number.isInteger(item.revision) && item.revision! > 0 ? item.revision! : 1,
        } as DemoIndicator;
      });
    }
  } catch {
    // Use the draft model catalog when browser storage is unavailable or invalid.
  }
  return initialIndicators;
}

export function saveDemoIndicators(indicators: DemoIndicator[]): void {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(indicators));
  } catch {
    // The page remains usable in memory when browser storage is unavailable.
  }
}
