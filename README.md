# نبض العالم | WorldPulse

تطبيق iPhone عربي للأخبار العالمية ومباريات اليوم، مبني باستخدام SwiftUI مع خدمة تجميع RSS وواجهة API-Football وجدولة تحديث عبر GitHub Actions.

## الوظائف
- خمس واجهات: الرئيسية، الأخبار، المباريات، التقرير الساعي، والمزيد.
- 15 مصدر RSS، تجميع وتصفية الأخبار المتشابهة، وعناوين مرتبطة بمصادرها الأصلية.
- الدوري العراقي والإسباني والإنجليزي ودوري أبطال أوروبا وكأس العالم وكأس آسيا وكأس أوروبا.
- تحديث الملف العام docs/feed.json مرة كل ساعة تقريباً، وحفظ آخر بيانات في الجهاز.
- معاينة تجريبية موسومة بوضوح عند عدم توفر بيانات حقيقية.

## التشغيل والبناء
1. افتح **Actions → Refresh news and fixtures → Run workflow** لتوليد ملف البيانات.
2. أضف API_FOOTBALL_KEY في **Settings → Secrets and variables → Actions** لتفعيل المباريات؛ الأخبار تعمل دون المفتاح.
3. من **Settings → Actions → General** فعّل صلاحيات Read and write لـ GITHUB_TOKEN لتحديث docs/feed.json.
4. افتح **Actions → Build unsigned IPA → Run workflow**، ثم حمّل WorldPulse-unsigned-IPA من Artifacts.
5. يلزم **توقيع قانوني صالح من Apple** لتثبيت IPA على iPhone. لا تضع مفاتيح API داخل التطبيق.

الموجز الساعي ليس إشعار Push مضموناً كل ساعة؛ جدولة GitHub قد تتأخر، ويتطلب التنبيه في الخلفية خادم APNs منفصلاً. تغطية مباريات اليوم تعتمد على الاشتراك وبيانات المزود.

## المصادر والتوثيق
- [API-Football](https://www.api-football.com/documentation_v3)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [Apple background tasks](https://developer.apple.com/documentation/backgroundtasks)
