import SwiftUI
import AVFoundation

struct ContentView: View {
    @StateObject private var store=FeedStore()
    @AppStorage("feedURL") private var feedURL=""
    @Environment(\.scenePhase) private var scenePhase
    @State private var selectedTab=0
    var body: some View {
        TabView(selection:$selectedTab) {
            NavigationStack { HomeScreen(store:store,selectedTab:$selectedTab) }
                .tabItem {Label("الرئيسية",systemImage:"house.fill")}.tag(0)
            NavigationStack { NewsScreen(store:store) }
                .tabItem {Label("الأخبار",systemImage:"newspaper.fill")}.tag(1)
            NavigationStack { MatchesScreen(store:store) }
                .tabItem {Label("المباريات",systemImage:"soccerball")}.tag(2)
            NavigationStack { ReportsScreen(store:store) }
                .tabItem {Label("التقارير",systemImage:"doc.text.fill")}.tag(3)
            NavigationStack { MoreScreen(store:store,feedURL:$feedURL) }
                .tabItem {Label("المزيد",systemImage:"ellipsis.circle.fill")}.tag(4)
        }
        .tint(Theme.blue)
        .preferredColorScheme(.dark)
        .environment(\.layoutDirection,.rightToLeft)
        .task {await store.refresh(feedURL:feedURL)}
        .onChange(of:scenePhase) { _,phase in
            if phase == .active {Task {await store.refresh(feedURL:feedURL)}}
        }
    }
}
struct Page<Content:View>:View {
    let title:String
    let content:Content
    init(title:String,@ViewBuilder content:()->Content) {
        self.title=title
        self.content=content()
    }
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:18) {
                if !title.isEmpty {
                    HStack {
                        Text(title).font(.system(size:27,weight:.bold))
                        Spacer()
                        Image(systemName:"globe.americas.fill").foregroundStyle(Theme.cyan)
                    }
                }
                content
            }
            .frame(maxWidth:.infinity,alignment:.leading)
            .padding(.horizontal,16)
            .padding(.top,18)
            .padding(.bottom,28)
        }
        .background(Theme.bg.ignoresSafeArea())
        .toolbar(.hidden,for:.navigationBar)
    }
}
struct SectionTitle:View {
    let title:String
    let symbol:String
    var body:some View {
        Label(title,systemImage:symbol)
            .font(.title3.bold())
            .foregroundStyle(.white)
    }
}
struct MessageBanner:View {
    let symbol:String
    let title:String
    var tint:Color = .orange
    var body:some View {
        Label(title,systemImage:symbol)
            .font(.footnote)
            .foregroundStyle(tint)
            .frame(maxWidth:.infinity,alignment:.leading)
            .padding(13)
            .background(tint.opacity(0.12),in:RoundedRectangle(cornerRadius:14))
    }
}
struct FeedMessage:View {
    @ObservedObject var store:FeedStore
    var body:some View {
        if store.feed?.preview == true {
            MessageBanner(symbol:"eye",title:"وضع المعاينة: الأخبار والمباريات المعروضة أمثلة وليست حقيقية",tint:Theme.cyan)
        } else if store.stale {
            MessageBanner(symbol:"clock",title:"البيانات قديمة أو غير مكتملة؛ تحقق من آخر تحديث")
        }
        if let error=store.error {
            MessageBanner(symbol:"wifi.exclamationmark",title:error)
        }
    }
}
struct TextHero:View {
    var body:some View {
        VStack(alignment:.leading,spacing:8) {
            Text("نبض العالم").font(.system(size:30,weight:.heavy))
            Text("WorldPulse • الأخبار والمباريات").font(.subheadline).foregroundStyle(Theme.cyan)
            Text("أخبار نصية فقط، من دون تنزيل أو تخزين الصور.")
                .font(.footnote).foregroundStyle(Theme.muted)
        }
        .frame(maxWidth:.infinity,alignment:.leading)
        .padding(19)
        .background(Theme.surface,in:RoundedRectangle(cornerRadius:19))
    }
}
struct ArticleRow:View {
    let article:Article
    @ObservedObject var store:FeedStore
    var body:some View {
        HStack(alignment:.top,spacing:12) {
            NavigationLink {
                ArticleDetail(article:article,store:store)
            } label: {
                VStack(alignment:.leading,spacing:8) {
                    Text(article.title).font(.subheadline.bold())
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal:false,vertical:true)
                    if !article.summary.isEmpty {
                        Text(article.summary).font(.footnote).foregroundStyle(Theme.muted)
                            .lineLimit(2)
                    }
                    Text("\(article.source) • \(article.category) • \(DateUtil.format(article.publishedAt,clock:false))")
                        .font(.caption2).foregroundStyle(Theme.cyan).lineLimit(2)
                }.frame(maxWidth:.infinity,alignment:.leading)
            }.buttonStyle(.plain)
            Button {store.toggleFavorite(article.id)} label: {
                Image(systemName:store.favorites.contains(article.id) ? "bookmark.fill":"bookmark")
                    .font(.body).foregroundStyle(Theme.cyan)
            }.accessibilityLabel("حفظ الخبر")
        }
        .padding(14)
        .background(Theme.surface,in:RoundedRectangle(cornerRadius:17))
    }
}
struct ArticleDetail:View {
    let article:Article
    @ObservedObject var store:FeedStore
    var body:some View {
        Page(title:"تفاصيل الخبر") {
            Text(article.title).font(.title2.bold()).fixedSize(horizontal:false,vertical:true)
            HStack {
                Label(article.source,systemImage:"newspaper")
                Spacer()
                Text(DateUtil.format(article.publishedAt,clock:false))
            }.font(.caption).foregroundStyle(Theme.cyan)
            Text(article.summary.isEmpty ? "افتح موقع المصدر للاطلاع على تفاصيل الخبر الأصلي." : article.summary)
                .font(.body).lineSpacing(7)
                .padding(18)
                .frame(maxWidth:.infinity,alignment:.leading)
                .background(Theme.surface,in:RoundedRectangle(cornerRadius:16))
            Text("هذا الملخص مقتطف من المصدر، وليس نص المقال الكامل.").font(.caption).foregroundStyle(Theme.muted)
            HStack {
                Button {
                    store.toggleFavorite(article.id)
                } label: {
                    Label(store.favorites.contains(article.id) ? "إزالة الحفظ":"حفظ الخبر",
                        systemImage:store.favorites.contains(article.id) ? "bookmark.fill":"bookmark")
                }
                .buttonStyle(.bordered)
                if let url=article.destination {
                    ShareLink(item:url) {Label("مشاركة",systemImage:"square.and.arrow.up")}
                        .buttonStyle(.bordered)
                    Link(destination:url) {
                        Label("المصدر",systemImage:"arrow.up.right")
                    }
                    .buttonStyle(.borderedProminent).tint(Theme.blue)
                }
            }
            if article.sourceCount>1 {
                Text("نشرته \(article.sourceCount) مصادر: \(article.relatedSources.joined(separator:"، "))")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
        }
    }
}
struct HomeScreen:View {
    @ObservedObject var store:FeedStore
    @Binding var selectedTab:Int
    var body:some View {
        Page(title:"") {
            TextHero()
            FeedMessage(store:store)
            HStack {
                SectionTitle(title:"أبرز الأخبار",symbol:"bolt.fill")
                Spacer()
                Button("عرض الكل") {selectedTab=1}
                    .font(.subheadline.bold()).foregroundStyle(Theme.cyan)
            }
            if let lead=store.feed?.news.first {
                NavigationLink {
                    ArticleDetail(article:lead,store:store)
                } label: {
                    VStack(alignment:.leading,spacing:9) {
                        Text("أبرز خبر").font(.caption.bold()).foregroundStyle(Theme.cyan)
                        Text(lead.title).font(.title3.bold())
                            .multilineTextAlignment(.leading).fixedSize(horizontal:false,vertical:true)
                        if !lead.summary.isEmpty {
                            Text(lead.summary).font(.footnote).foregroundStyle(Theme.muted).lineLimit(3)
                        }
                        Text("\(lead.source) • \(lead.category)").font(.caption).foregroundStyle(Theme.cyan)
                    }
                    .frame(maxWidth:.infinity,alignment:.leading)
                    .padding(16)
                    .background(Theme.surface,in:RoundedRectangle(cornerRadius:20))
                }.buttonStyle(.plain)
            }
            ForEach(Array((store.feed?.news ?? []).dropFirst().prefix(6))) { article in
                ArticleRow(article:article,store:store)
            }
            HStack {
                SectionTitle(title:"مباريات اليوم",symbol:"soccerball")
                Spacer()
                Button("جميع المباريات") {selectedTab=2}
                    .font(.caption.bold()).foregroundStyle(Theme.cyan)
            }
            ForEach(Array((store.feed?.matches ?? []).prefix(3))) { match in
                MatchRow(match:match)
            }
            if store.feed?.news.isEmpty != false {
                MessageBanner(symbol:"news",title:"لا توجد أخبار منشورة بعد؛ شغّل تحديث البيانات من GitHub Actions.",tint:Theme.muted)
            }
        }
    }
}
struct Chip:View {
    let text:String
    let selected:Bool
    let action:()->Void
    var body:some View {
        Button(action:action) {Text(text).font(.caption.bold()).lineLimit(1).padding(.horizontal,13).padding(.vertical,11)}
            .foregroundStyle(selected ? .white : Theme.muted)
            .background(selected ? Theme.blue : Theme.surface,in:Capsule())
            .buttonStyle(.plain)
    }
}
struct NewsScreen:View {
    @ObservedObject var store:FeedStore
    @State private var search=""
    @State private var category="الكل"
    let categories=["الكل","العالم","سياسة","اقتصاد","تقنية","رياضة"]
    var results:[Article] {
        (store.feed?.news ?? []).filter { a in
            (category=="الكل" || a.category==category) &&
            (search.isEmpty || a.title.localizedCaseInsensitiveContains(search) || a.summary.localizedCaseInsensitiveContains(search) || a.source.localizedCaseInsensitiveContains(search))
        }
    }
    var body:some View {
        Page(title:"الأخبار العالمية") {
            FeedMessage(store:store)
            HStack {
                Image(systemName:"magnifyingglass").foregroundStyle(Theme.muted)
                TextField("ابحث في الأخبار...",text:$search)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }.padding(14).background(Theme.surface,in:RoundedRectangle(cornerRadius:14))
            ScrollView(.horizontal,showsIndicators:false) {
                HStack {
                    ForEach(categories,id:\.self) { c in
                        Chip(text:c,selected:category==c){category=c}
                    }
                }
            }
            HStack {
                SectionTitle(title:"آخر الأخبار",symbol:"newspaper.fill")
                Spacer()
                Text("\(results.count) خبراً").font(.caption).foregroundStyle(Theme.muted)
            }
            LazyVStack(spacing:11) {
                ForEach(results) { article in
                    ArticleRow(article:article,store:store)
                }
            }
            if results.isEmpty {
                MessageBanner(symbol:"line.3.horizontal.decrease.circle",title:"لا توجد نتائج لهذا البحث أو التصنيف.",tint:Theme.muted)
            }
        }
    }
}
struct MatchRow:View {
    let match:FootballMatch
    var completed:Bool {["FT","AET","PEN"].contains(match.status)}
    var live:Bool {["1H","HT","2H","ET","BT","P","LIVE"].contains(match.status)}
    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack {
                Label(match.league,systemImage:"sportscourt")
                    .font(.caption.bold()).foregroundStyle(Theme.cyan)
                Spacer()
                Text(live ? "● مباشر" : completed ? "انتهت":"\(DateUtil.format(match.kickoff))")
                    .font(.caption.bold()).foregroundStyle(live ? .red : Theme.muted)
            }
            HStack(spacing:8) {
                Text(match.home).frame(maxWidth:.infinity,alignment:.leading)
                VStack(spacing:4) {
                    Text(match.homeGoals == nil && match.awayGoals == nil ? "VS" : "\(match.homeGoals ?? 0) : \(match.awayGoals ?? 0)")
                        .font(.title3.bold()).monospacedDigit()
                    Text(match.status).font(.caption2).foregroundStyle(Theme.muted)
                }.frame(width:85)
                Text(match.away).frame(maxWidth:.infinity,alignment:.trailing)
            }.font(.subheadline.bold())
        }
        .padding(16)
        .background(Theme.surface,in:RoundedRectangle(cornerRadius:18))
    }
}
struct MatchesScreen:View {
    @ObservedObject var store:FeedStore
    @State private var competition="all"
    var filtered:[FootballMatch] {
        (store.feed?.matches ?? []).filter {competition=="all" || $0.competitionId==competition}
    }
    var body:some View {
        Page(title:"مباريات اليوم") {
            FeedMessage(store:store)
            VStack(alignment:.leading,spacing:8) {
                SectionTitle(title:"جدول المباريات",symbol:"calendar")
                Text("بتوقيت بغداد 🇮🇶 • \(store.feed?.localDate ?? DateUtil.today())")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
            .frame(maxWidth:.infinity,alignment:.leading)
            .padding(18).background(Theme.surface,in:RoundedRectangle(cornerRadius:18))
            ScrollView(.horizontal,showsIndicators:false) {
                HStack {
                    Chip(text:"جميع البطولات",selected:competition=="all"){competition="all"}
                    ForEach(store.feed?.competitions ?? []) { lg in
                        Chip(text:lg.name,selected:competition==lg.id){competition=lg.id}
                    }
                }
            }
            if store.feed?.sportsStatus=="not_configured" {
                MessageBanner(symbol:"key",title:"لإظهار مباريات حقيقية أضف API_FOOTBALL_KEY إلى أسرار GitHub Actions.",tint:Theme.muted)
            } else if store.feed?.sportsStatus=="error" {
                MessageBanner(symbol:"wifi.exclamationmark",title:store.feed?.sportsError ?? "تعذر جلب المباريات")
            }
            LazyVStack(spacing:11) {
                ForEach(filtered) {match in MatchRow(match:match)}
            }
            if filtered.isEmpty {
                MessageBanner(symbol:"calendar.badge.exclamationmark",title:"لا توجد مباريات مدرجة لهذه البطولة اليوم، أو لم تتوفر من المصدر.",tint:Theme.muted)
            }
            Text("تُحدّث البيانات كل ساعة تقريباً. النتائج أثناء المباراة قد تتأخر؛ ليست بثاً لحظياً.")
                .font(.caption).foregroundStyle(Theme.muted)
        }
    }
}
struct ReportsScreen:View {
    @ObservedObject var store:FeedStore
    @State private var speaker=AVSpeechSynthesizer()
    @State private var speaking=false
    var body:some View {
        Page(title:"التقرير الساعي") {
            FeedMessage(store:store)
            ZStack {
                RoundedRectangle(cornerRadius:24)
                    .fill(LinearGradient(colors:[Theme.blue.opacity(0.7),Theme.surface,Theme.bg],startPoint:.topLeading,endPoint:.bottomTrailing))
                VStack(spacing:10) {
                    Image(systemName:"globe.europe.africa.fill")
                        .font(.system(size:62)).foregroundStyle(Theme.cyan)
                    Text("الموجز الإخباري الساعي").font(.title2.bold())
                    Text("أهم \(store.feed?.digest.count ?? 0) عناوين حول العالم")
                        .font(.subheadline).foregroundStyle(Theme.muted)
                    if let generated=store.feed?.generatedAt {
                        Text("آخر تحديث: \(DateUtil.format(generated,clock:false))، \(DateUtil.format(generated))")
                            .font(.caption).foregroundStyle(Theme.muted)
                    }
                    Button {
                        if speaker.isSpeaking {
                            speaker.stopSpeaking(at:.immediate)
                            speaking=false
                        } else {
                            let script=(store.feed?.digest ?? []).map(\.headline).joined(separator:". ")
                            guard !script.isEmpty else {return}
                            let utterance=AVSpeechUtterance(string:script)
                            utterance.voice=AVSpeechSynthesisVoice(language:"ar-SA")
                            utterance.rate=0.47
                            speaker.speak(utterance)
                            speaking=true
                        }
                    } label: {
                        Label(speaking ? "إيقاف القراءة":"استمع للعناوين",systemImage:speaking ? "stop.fill":"play.fill")
                            .font(.headline).padding(.horizontal,16).padding(.vertical,12)
                    }
                    .buttonStyle(.borderedProminent).tint(Theme.blue)
                }
                .padding(25)
                .frame(maxWidth:.infinity)
            }
            SectionTitle(title:"عناوين التقرير",symbol:"list.number")
            ForEach(Array((store.feed?.digest ?? []).indices),id:\.self) { i in
                if let story=store.feed?.digest[i] {
                HStack(alignment:.top,spacing:12) {
                    Text("\(i+1)")
                        .font(.headline.bold()).foregroundStyle(.white)
                        .frame(width:31,height:31)
                        .background(Theme.raised,in:Circle())
                    VStack(alignment:.leading,spacing:7) {
                        Text(story.headline).font(.subheadline.bold())
                        Text("\(story.source) • \(story.category)")
                            .font(.caption).foregroundStyle(Theme.muted)
                        if let url=story.destination {
                            Link("قراءة الخبر الأصلي",destination:url)
                                .font(.caption.bold()).foregroundStyle(Theme.cyan)
                        }
                    }
                    Spacer()
                }
                .padding(13).background(Theme.surface,in:RoundedRectangle(cornerRadius:15))
                }
            }
            Text(store.feed?.digestNote ?? "تعذر تحميل التقرير")
                .font(.caption).foregroundStyle(Theme.muted)
        }
    }
}
struct MoreScreen:View {
    @ObservedObject var store:FeedStore
    @Binding var feedURL:String
    var body:some View {
        Page(title:"المزيد والإعدادات") {
            FeedMessage(store:store)
            NavigationLink {
                FavoritesScreen(store:store)
            } label: {
                HStack {
                    Label("الأخبار المحفوظة",systemImage:"bookmark.fill")
                    Spacer()
                    Text("\(store.favorites.count)").foregroundStyle(Theme.cyan)
                    Image(systemName:"chevron.left").foregroundStyle(Theme.muted)
                }.font(.headline).padding(18).background(Theme.surface,in:RoundedRectangle(cornerRadius:18))
            }.buttonStyle(.plain)
            VStack(alignment:.leading,spacing:12) {
                SectionTitle(title:"مصدر البيانات",symbol:"link")
                TextField("رابط feed.json (HTTPS)",text:$feedURL,axis:.vertical)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .lineLimit(2...3)
                    .font(.footnote)
                    .padding(13)
                    .background(Theme.raised,in:RoundedRectangle(cornerRadius:12))
                Text("الافتراضي: ملف الأخبار العام المنشور في مستودع Sport-News.")
                    .font(.caption).foregroundStyle(Theme.muted)
                Button {
                    Task {await store.refresh(feedURL:feedURL,force:true)}
                } label: {
                    Label(store.loading ? "جارِ التحديث...":"تحديث الأخبار والمباريات",systemImage:"arrow.clockwise")
                        .frame(maxWidth:.infinity).padding(5)
                }
                .buttonStyle(.borderedProminent).tint(Theme.blue)
                .disabled(store.loading)
            }.padding(18).background(Theme.surface,in:RoundedRectangle(cornerRadius:18))
            VStack(alignment:.leading,spacing:10) {
                SectionTitle(title:"حول التطبيق",symbol:"info.circle")
                Text("WorldPulse • إصدار 0.4")
                Text("موجز أخبار تلقائي من مصادر RSS، وجدول مباريات اليوم من API-Football. تعرض الخدمة بيانات من ناشريها الأصليين وروابطهم.")
                Text("توفير مساحة التخزين: الأخبار لا تُحفظ على الهاتف، ولا يتم تنزيل صور، بل تحتفظ الذاكرة المؤقتة RAM بالنصوص أثناء الاستخدام. تُحفظ معرّفات المفضلة والإعدادات الصغيرة فقط.")
                Text("الإشعارات الفورية غير مفعلة في هذا الإصدار؛ يتطلب إرسالها من الخادم إعداد Apple Push Notifications.")
                Text("مواعيد تحديث GitHub Actions تقريبية، وقد تتأخر عند ضغط الخدمة.")
                Link("المشروع على GitHub",destination:URL(string:"https://github.com/AbbasSabah97/Sport-News")!)
                    .foregroundStyle(Theme.cyan)
            }
            .font(.footnote).foregroundStyle(Theme.muted)
            .padding(18).frame(maxWidth:.infinity,alignment:.leading)
            .background(Theme.surface,in:RoundedRectangle(cornerRadius:18))
        }
    }
}
struct FavoritesScreen:View {
    @ObservedObject var store:FeedStore
    var body:some View {
        Page(title:"الأخبار المحفوظة") {
            let items=(store.feed?.news ?? []).filter {store.favorites.contains($0.id)}
            if items.isEmpty {
                MessageBanner(symbol:"bookmark",title:"لم تحفظ أخباراً بعد، أو أن أخبارك المحفوظة لم تعد ضمن آخر موجز.",tint:Theme.muted)
            }
            ForEach(items) {article in ArticleRow(article:article,store:store)}
        }
    }
}
