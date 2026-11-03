package com.worldpulse.daily;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.content.res.Configuration;
import android.graphics.PorterDuff;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import org.json.*;
import java.time.*;
import java.time.format.*;
import java.util.*;

public class MainActivity extends Activity {
  // Travel palette: #2B3D54 #2C5B61 #247065 #60A65F #FFEC97.
  // All UI colors use semantic roles and follow system light/dark mode.
  static int NAVY,ORANGE,SKY,BG,WHITE,MUTED,PALE,GREEN,LIME,YELLOW,MIDBLUE,ON_ACTION;
  private boolean darkMode=false;
  private final Handler liveHandler=new Handler(Looper.getMainLooper());
  private long lastScorePoll=0;
  private boolean foreground=false;
  private final Runnable liveTicker=new Runnable(){
    @Override public void run(){
      if(!foreground)return;
      if(online && !loading && System.currentTimeMillis()-lastScorePoll>55000)refreshScores();
      liveHandler.postDelayed(this,60000);
    }
  };
  private void palette(){
    darkMode=(getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
        ==Configuration.UI_MODE_NIGHT_YES;
    MIDBLUE=Color.rgb(44,91,97);      // #2C5B61
    LIME=Color.rgb(96,166,95);        // #60A65F
    YELLOW=Color.rgb(255,236,151);    // #FFEC97
    GREEN=LIME;
    if(darkMode){
      BG=Color.rgb(19,34,45);
      WHITE=Color.rgb(29,51,59);
      SKY=Color.rgb(42,72,74);
      NAVY=Color.rgb(242,249,246);
      MUTED=Color.rgb(177,204,198);
      PALE=Color.rgb(47,84,76);
      ORANGE=LIME;
      ON_ACTION=Color.rgb(22,44,47);
    }else{
      BG=Color.rgb(245,248,246);
      WHITE=Color.WHITE;
      SKY=Color.rgb(229,240,236);
      NAVY=Color.rgb(43,61,84);     // #2B3D54
      MUTED=Color.rgb(77,112,112);
      PALE=Color.rgb(236,247,232);
      ORANGE=Color.rgb(36,112,101); // #247065
      ON_ACTION=Color.WHITE;
    }
  }
  static final ZoneId ZONE=ZoneId.of("Asia/Baghdad");
  static final String[] IDS={"iraq","spain","england","ucl","worldcup","euro","asiacup"};
  static final String[] LEAGUES={"دوري نجوم العراق","الدوري الإسباني","الدوري الإنجليزي الممتاز",
       "دوري أبطال أوروبا","كأس العالم FIFA","كأس أمم أوروبا","كأس أمم آسيا"};
  static final String[] ICONS={"IQ","LL","PL","CL","WC","EU","AFC"};
  static final String[] TABS={"الرئيسية","المباريات","البطولات","المتابعة","المزيد"};
  static final int[] TAB_ICONS={R.drawable.ic_nav_home,R.drawable.ic_nav_matches,
      R.drawable.ic_nav_trophy,R.drawable.ic_nav_star,R.drawable.ic_nav_settings};
  final FeedClient client=new FeedClient();
  JSONObject data=new JSONObject(), match=null;
  SharedPreferences prefs;
  Set<String> following=new HashSet<>();
  LinearLayout page;
  ScrollView activeScroll;
  int tab=0,day=-1,detailTab=0,leagueTab=0;
  String league="all",leaguePage=null,teamPage=null,error=null;
  boolean online=false,loading=false;

  @Override public void onCreate(Bundle b){
    super.onCreate(b);
    palette();
    if(android.os.Build.VERSION.SDK_INT>=29)getWindow().getDecorView().setForceDarkAllowed(false);
    getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(WHITE);
    getWindow().getDecorView().setSystemUiVisibility(darkMode?0:
        View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    prefs=getSharedPreferences("football_follows",MODE_PRIVATE);
    following.addAll(prefs.getStringSet("teams",new HashSet<>()));
    try(java.io.InputStream in=getAssets().open("preview-feed.json");
        java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream()){
      byte[] bfr=new byte[2048];int n;
      while((n=in.read(bfr))>=0 && out.size()+n<30000)out.write(bfr,0,n);
      data=new JSONObject(out.toString("UTF-8"));
    }catch(Exception ignored){}
    render();refresh();
  }
  int dp(int x){return Math.round(x*getResources().getDisplayMetrics().density);}
  GradientDrawable fill(int color,int r){
    GradientDrawable g=new GradientDrawable();g.setColor(color);g.setCornerRadius(dp(r));return g;
  }
  GradientDrawable gradient(int c1,int c2,int r){
    GradientDrawable g=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{c1,c2});
    g.setCornerRadius(dp(r));return g;
  }
  LinearLayout col(){LinearLayout a=new LinearLayout(this);a.setOrientation(1);a.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);return a;}
  LinearLayout row(){LinearLayout a=new LinearLayout(this);a.setOrientation(0);a.setGravity(Gravity.CENTER_VERTICAL);a.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);return a;}
  TextView txt(String s,int size,boolean bold,int color){
    TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);
    t.setTextDirection(View.TEXT_DIRECTION_FIRST_STRONG);t.setGravity(Gravity.CENTER_VERTICAL);
    t.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));return t;
  }
  void add(LinearLayout p,View v){p.addView(v,new LinearLayout.LayoutParams(-1,-2));}
  void wt(LinearLayout p,View v,int w){p.addView(v,new LinearLayout.LayoutParams(0,-2,w));}
  void gap(LinearLayout p,int n){View v=new View(this);p.addView(v,new LinearLayout.LayoutParams(1,dp(n)));}
  void card(LinearLayout p,LinearLayout c){
    c.setPadding(dp(16),dp(16),dp(16),dp(16));c.setBackground(fill(WHITE,20));
    c.setElevation(dp(1));
    LinearLayout.LayoutParams par=new LinearLayout.LayoutParams(-1,-2);par.bottomMargin=dp(10);p.addView(c,par);
  }
  TextView pill(String s,boolean active,Runnable action){
    TextView t=txt(s,13,active,active?ON_ACTION:NAVY);
    t.setGravity(Gravity.CENTER);t.setPadding(dp(12),dp(10),dp(12),dp(10));
    t.setBackground(fill(active?ORANGE:SKY,14));t.setOnClickListener(v->action.run());return t;
  }
  void chip(LinearLayout parent,String s,boolean active,Runnable action){
    TextView b=pill(s,active,action);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2);
    p.setMargins(dp(3),0,dp(3),0);parent.addView(b,p);
  }
  void scrollChips(LinearLayout chips){
    HorizontalScrollView s=new HorizontalScrollView(this);s.setHorizontalScrollBarEnabled(false);s.addView(chips);add(page,s);gap(page,14);
  }
  void heading(String s,String more,Runnable action){
    LinearLayout r=row();wt(r,txt(s,19,true,NAVY),1);
    if(more!=null){TextView v=txt(more+"  ‹",12,true,ORANGE);v.setOnClickListener(w->action.run());r.addView(v);}
    add(page,r);gap(page,11);
  }
  ImageView vector(int res,int color,int size){
    ImageView v=new ImageView(this);
    v.setImageResource(res);
    v.setColorFilter(color,PorterDuff.Mode.SRC_IN);
    v.setScaleType(ImageView.ScaleType.FIT_CENTER);
    v.setLayoutParams(new LinearLayout.LayoutParams(dp(size),dp(size)));
    return v;
  }
  TextView leagueEmblem(String code,int size){
    TextView emblem=txt(leagueIcon(code),size<=44?11:13,true,darkMode?YELLOW:NAVY);
    emblem.setGravity(Gravity.CENTER);
    emblem.setBackground(fill(darkMode?SKY:PALE,16));
    emblem.setWidth(dp(size));emblem.setHeight(dp(size));
    return emblem;
  }
  void toolbar(String label){
    LinearLayout bar=row();
    ImageView logo=vector(R.drawable.ic_nav_matches,ORANGE,27);
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(dp(27),dp(27));
    lp.leftMargin=dp(11);bar.addView(logo,lp);
    wt(bar,txt("WorldPulse",26,true,NAVY),1);
    TextView badge=txt("LIVE",11,true,darkMode?NAVY:MIDBLUE);
    badge.setPadding(dp(12),dp(9),dp(12),dp(9));
    badge.setBackground(fill(darkMode?SKY:PALE,14));bar.addView(badge);
    add(page,bar);
    add(page,txt("FOOTBALL  •  "+label,11,true,MUTED));gap(page,17);
  }
  void message(String s){
    TextView v=txt(s,13,false,NAVY);v.setPadding(dp(12),dp(13),dp(12),dp(13));
    v.setBackground(fill(PALE,13));add(page,v);gap(page,11);
  }
  void blank(String s){
    LinearLayout c=col();c.setGravity(Gravity.CENTER);
    TextView icon=txt("⚽",27,true,ORANGE);icon.setGravity(Gravity.CENTER);add(c,icon);gap(c,8);
    TextView t=txt(s,14,false,MUTED);t.setGravity(Gravity.CENTER);add(c,t);card(page,c);
  }
  void liveBanner(){
    int live=0;
    JSONArray games=list("matches");
    for(int i=0;i<games.length();i++){
      String state=at(games,i).optString("status","NS");
      if(state.equals("LIVE")||state.equals("1H")||state.equals("2H")||state.equals("HT"))live++;
    }
    if(live>0){
      LinearLayout strip=row();
      wt(strip,txt("●  "+live+" مباراة جارية حالياً",14,true,GREEN),1);
      TextView t=txt("عرض المباريات  ‹",12,true,ORANGE);
      t.setOnClickListener(v->{tab=1;day=-1;render();});
      strip.addView(t);card(page,strip);
    }
  }
  void reloadNotice(){
    if(!online)message("بيانات تجريبية إلى حين اتصال التطبيق بمصدر المباريات.");
    if(error!=null)message(error);
    String updated=data.optString("sports_source_updated_at",
        data.optString("sports_updated_at",data.optString("generated_at","")));
    try{
      java.time.Instant when=OffsetDateTime.parse(updated).toInstant();
      long age=java.time.Duration.between(when,java.time.Instant.now()).toMinutes();
      if(age>10)message("آخر تحديث للمباريات منذ "+age+" دقيقة؛ النتائج قد تكون متأخرة.");
    }catch(Exception ignored){}
    try{
      if(!LocalDate.parse(data.optString("week_start")).equals(LocalDate.now(ZONE)))
        message("الجدول قديم؛ اضغط تحديث للحصول على مباريات الأسبوع الحالي.");
    }catch(Exception ignored){}
  }
  JSONArray list(String k){JSONArray a=data.optJSONArray(k);return a==null?new JSONArray():a;}
  JSONObject at(JSONArray a,int i){JSONObject v=a.optJSONObject(i);return v==null?new JSONObject():v;}
  LocalDate local(String iso){
    try{return OffsetDateTime.parse(iso).atZoneSameInstant(ZONE).toLocalDate();}
    catch(Exception e){return null;}
  }
  String time(String iso){
    try{return OffsetDateTime.parse(iso).atZoneSameInstant(ZONE).format(DateTimeFormatter.ofPattern("HH:mm"));}
    catch(Exception e){return "--:--";}
  }
  String date(LocalDate d){
    return d==null?"موعد غير محدد":d.format(DateTimeFormatter.ofPattern("EEEE، d MMMM",new Locale("ar","IQ")));
  }
  String leagueName(String code){
    for(int i=0;i<IDS.length;i++)if(IDS[i].equals(code))return LEAGUES[i];
    return code;
  }
  String leagueIcon(String code){
    for(int i=0;i<IDS.length;i++)if(IDS[i].equals(code))return ICONS[i];return "⚽";
  }
  boolean isLiveStatus(String s){
    return s.equals("LIVE")||s.equals("1H")||s.equals("2H")||s.equals("HT")
        ||s.equals("ET")||s.equals("BT")||s.equals("P");
  }
  String status(String s){
    if(s.equals("NS"))return "لم تبدأ";if(s.equals("FT")||s.equals("AET")||s.equals("PEN"))return "انتهت";
    if(s.equals("PST"))return "مؤجلة";if(s.equals("CANC"))return "ملغاة";if(s.equals("HT"))return "استراحة";
    if(s.equals("1H")||s.equals("2H")||s.equals("LIVE"))return "● مباشر";return s;
  }
  String team(String x){
    if(x==null)return "—";
    switch(x.toLowerCase(Locale.ROOT)){
      case "real madrid":return "ريال مدريد";case "fc barcelona":case "barcelona":return "برشلونة";
      case "arsenal":return "أرسنال";case "chelsea":return "تشيلسي";case "liverpool":return "ليفربول";
      case "manchester city":return "مانشستر سيتي";case "manchester united":return "مانشستر يونايتد";
      case "villarreal":return "فياريال";case "espanyol":return "إسبانيول";
      case "bayern munich":return "بايرن ميونخ";case "atletico madrid":return "أتلتيكو مدريد";
      case "aek athens":return "أيك أثينا";
      case "afc bournemouth":return "بورنموث";
      case "as roma":return "روما";
      case "alavés":return "ألافيس";
      case "aston villa":return "أستون فيلا";
      case "athletic club":return "أتلتيك بلباو";
      case "brentford":return "برينتفورد";
      case "brighton & hove albion":return "برايتون";
      case "celta vigo":return "سيلتا فيغو";
      case "club brugge":return "كلوب بروج";
      case "como":return "كومو";
      case "coventry city":return "كوفنتري سيتي";
      case "crystal palace":return "كريستال بالاس";
      case "deportivo":return "ديبورتيفو";
      case "elche":return "إلتشي";
      case "everton":return "إيفرتون";
      case "fc porto":return "بورتو";
      case "fenerbahce":return "فنربخشة";
      case "feyenoord rotterdam":return "فينورد";
      case "fulham":return "فولهام";
      case "galatasaray":return "غلطة سراي";
      case "getafe":return "خيتافي";
      case "hull city":return "هال سيتي";
      case "internazionale":return "إنتر ميلان";
      case "ipswich town":return "إيبسويتش تاون";
      case "lask linz":return "لاسك لينتس";
      case "leeds united":return "ليدز يونايتد";
      case "lens":return "لانس";
      case "levante":return "ليفانتي";
      case "lille":return "ليل";
      case "málaga":return "ملقة";
      case "napoli":return "نابولي";
      case "newcastle united":return "نيوكاسل يونايتد";
      case "nottingham forest":return "نوتنغهام فورست";
      case "osasuna":return "أوساسونا";
      case "psv eindhoven":return "آيندهوفن";
      case "paris saint-germain":return "باريس سان جيرمان";
      case "rb leipzig":return "لايبزيغ";
      case "racing santander":return "راسينغ سانتاندير";
      case "rayo vallecano":return "رايو فاييكانو";
      case "real betis":return "ريال بيتيس";
      case "real sociedad":return "ريال سوسيداد";
      case "sabah fk":return "صباح";
      case "sevilla":return "إشبيلية";
      case "shakhtar donetsk":return "شاختار دونيتسك";
      case "slavia prague":return "سلافيا براغ";
      case "slovan bratislava":return "سلوفان براتيسلافا";
      case "sporting cp":return "سبورتينغ لشبونة";
      case "sunderland":return "سندرلاند";
      case "tottenham hotspur":return "توتنهام";
      case "valencia":return "فالنسيا";
      case "vfb stuttgart":return "شتوتغارت";
      case "viking fk":return "فايكنغ";
      case "bodo/glimt":return "بودو غليمت";
      case "borussia dortmund":return "بوروسيا دورتموند";
      case "atlético madrid":return "أتلتيكو مدريد";
      case "al shorta":return "الشرطة";case "al zawraa":return "الزوراء";case "al talaba":return "الطلبة";
      default:return x;
    }
  }
  String score(JSONObject m){
    return !m.isNull("home_goals")&&!m.isNull("away_goals")
        ?m.optInt("home_goals")+" : "+m.optInt("away_goals"):time(m.optString("kickoff"));
  }
  void render(){
    LinearLayout root=col();root.setBackgroundColor(BG);setContentView(root);
    ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setVerticalScrollBarEnabled(false);
    activeScroll=scroll;
    root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
    page=col();page.setPadding(dp(16),dp(17),dp(16),dp(25));
    scroll.addView(page,new ScrollView.LayoutParams(-1,-2));
    if(match!=null)matchPage();
    else if(teamPage!=null)teamDetails();
    else if(leaguePage!=null)leagueDetails();
    else if(tab==0)home();
    else if(tab==1)matches();
    else if(tab==2)competitions();
    else if(tab==3)favorites();
    else settings();
    LinearLayout nav=row();nav.setBackground(fill(WHITE,0));nav.setPadding(dp(3),dp(8),dp(3),dp(8));
    for(int i=0;i<TABS.length;i++){
      final int k=i;LinearLayout item=col();item.setGravity(Gravity.CENTER);
      boolean selected=tab==i&&match==null&&teamPage==null&&leaguePage==null;
      ImageView ic=vector(TAB_ICONS[i],selected?ORANGE:MUTED,23);
      LinearLayout iconWrap=row();iconWrap.setGravity(Gravity.CENTER);
      iconWrap.setPadding(dp(14),dp(7),dp(14),dp(7));
      iconWrap.setBackground(fill(selected?(darkMode?SKY:PALE):WHITE,16));
      iconWrap.addView(ic);add(item,iconWrap);
      TextView lb=txt(TABS[i],11,selected,selected?ORANGE:MUTED);
      lb.setGravity(Gravity.CENTER);add(item,lb);
      item.setOnClickListener(v->{tab=k;match=null;teamPage=null;leaguePage=null;render();});
      nav.addView(item,new LinearLayout.LayoutParams(0,dp(68),1));
    }
    add(root,nav);
  }
  void home(){
    LinearLayout hero=col();hero.setPadding(dp(22),dp(23),dp(22),dp(23));
    hero.setBackground(gradient(Color.rgb(43,61,84),Color.rgb(44,91,97),24));
    add(hero,txt("WorldPulse",30,true,Color.WHITE));
    gap(hero,3);
    add(hero,txt("عالم كرة القدم بين يديك",18,true,YELLOW));gap(hero,9);
    add(hero,txt("سبع بطولات  •  مباريات مباشرة  •  توقيت بغداد",12,false,Color.WHITE));
    add(page,hero);gap(page,18);
    heading("البطولات", "الكل",()->{tab=2;render();});
    LinearLayout quick=row();
    for(int i=0;i<4;i++){
      final String id=IDS[i];
      LinearLayout box=col();box.setGravity(Gravity.CENTER);box.setBackground(fill(WHITE,14));
      TextView e=leagueEmblem(id,42);e.setGravity(Gravity.CENTER);add(box,e);
      TextView n=txt(new String[]{"العراقي","LaLiga","Premier","Champions"}[i],11,true,NAVY);
      n.setGravity(Gravity.CENTER);add(box,n);
      box.setOnClickListener(v->{leaguePage=id;leagueTab=0;render();});
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(75),1);
      p.setMargins(dp(3),0,dp(3),0);quick.addView(box,p);
    }
    add(page,quick);gap(page,20);
    heading("مباريات هذا الأسبوع","عرض الكل",()->{tab=1;day=-1;render();});
    liveBanner();
    reloadNotice();
    JSONArray fixtures=list("matches");int count=0;
    for(int i=0;i<fixtures.length()&&count<8;i++){
      JSONObject m=at(fixtures,i);LocalDate d=local(m.optString("kickoff"));
      if(d==null||d.isBefore(LocalDate.now(ZONE))||d.isAfter(LocalDate.now(ZONE).plusDays(6)))continue;
      matchCard(page,m,true);count++;
    }
    if(count==0)blank("لا تتوفر مباريات معلنة لهذا الأسبوع في المصدر.");
    gap(page,14);heading("آخر أخبار كرة القدم",null,null);
    JSONArray news=list("news");count=0;
    for(int i=0;i<news.length()&&count<4;i++){
      JSONObject story=at(news,i);
      if(!"رياضة".equals(story.optString("category")))continue;
      LinearLayout c=col();add(c,txt(story.optString("title"),14,true,NAVY));gap(c,7);
      add(c,txt(story.optString("source"),11,false,MUTED));
      c.setOnClickListener(v->open(story.optString("url")));card(page,c);count++;
    }
    if(count==0)blank("لا توجد أخبار رياضية عربية حديثة في الموجز.");
  }
  void matchCard(LinearLayout target,JSONObject m,boolean showLeague){
    LinearLayout c=col();
    if(showLeague){
      LinearLayout r=row();
      String code=m.optString("competition_id");
      TextView emblem=leagueEmblem(code,32);
      LinearLayout.LayoutParams eb=new LinearLayout.LayoutParams(dp(32),dp(32));eb.leftMargin=dp(9);
      r.addView(emblem,eb);
      wt(r,txt(leagueName(code),12,true,NAVY),1);
      r.addView(txt(date(local(m.optString("kickoff"))),11,false,MUTED));add(c,r);gap(c,11);
    }
    LinearLayout teams=row();
    TextView home=txt(team(m.optString("home")),14,true,NAVY),away=txt(team(m.optString("away")),14,true,NAVY);
    home.setGravity(Gravity.CENTER);away.setGravity(Gravity.CENTER);
    TextView points=txt(score(m),18,true,darkMode?YELLOW:ORANGE);points.setGravity(Gravity.CENTER);
    wt(teams,home,12);wt(teams,points,8);wt(teams,away,12);add(c,teams);gap(c,9);
    LinearLayout bottom=row();
    boolean live=isLiveStatus(m.optString("status","NS"));
    wt(bottom,txt(status(m.optString("status","NS")),11,true,live?GREEN:MUTED),1);
    bottom.addView(txt(time(m.optString("kickoff"))+" • بغداد",11,false,MUTED));
    add(c,bottom);c.setOnClickListener(v->{match=m;detailTab=0;render();});card(target,c);
  }
  void dates(){
    LinearLayout r=row();chip(r,"الأسبوع",day==-1,()->{day=-1;render();});
    for(int i=0;i<7;i++){
      final int n=i;LocalDate date=LocalDate.now(ZONE).plusDays(i);
      String label=i==0?"اليوم":i==1?"غداً":date.format(DateTimeFormatter.ofPattern("EEE dd",new Locale("ar","IQ")));
      chip(r,label,day==i,()->{day=n;render();});
    }
    scrollChips(r);
  }
  void filters(){
    LinearLayout r=row();chip(r,"كل البطولات",league.equals("all"),()->{league="all";render();});
    for(int i=0;i<IDS.length;i++){
      final String id=IDS[i];chip(r,ICONS[i]+" "+LEAGUES[i],league.equals(id),()->{league=id;render();});
    }
    scrollChips(r);
  }
  void matches(){
    toolbar("المباريات");heading("جدول المباريات",null,null);
    dates();filters();liveBanner();reloadNotice();JSONArray a=list("matches");
    LocalDate last=null;int count=0;
    for(int i=0;i<a.length();i++){
      JSONObject m=at(a,i);LocalDate d=local(m.optString("kickoff"));
      if(d==null)continue;
      if(!league.equals("all")&&!league.equals(m.optString("competition_id")))continue;
      if(day==-1?(d.isBefore(LocalDate.now(ZONE))||d.isAfter(LocalDate.now(ZONE).plusDays(6))):
          !d.equals(LocalDate.now(ZONE).plusDays(day)))continue;
      if(!d.equals(last)){add(page,txt("◷  "+date(d),14,true,NAVY));gap(page,9);last=d;}
      matchCard(page,m,true);count++;
    }
    if(count==0)blank("لا توجد مباريات مؤكدة للفترة المختارة. قد لا تتوفر تغطية جميع الدوريات.");
  }
  void competitions(){
    toolbar("البطولات");heading("البطولات السبع",null,null);
    for(int i=0;i<IDS.length;i++){
      final String id=IDS[i];LinearLayout c=row();
      TextView emblem=leagueEmblem(id,48);
      LinearLayout.LayoutParams emblemParams=new LinearLayout.LayoutParams(dp(48),dp(48));
      emblemParams.leftMargin=dp(15);c.addView(emblem,emblemParams);
      LinearLayout sub=col();add(sub,txt(LEAGUES[i],16,true,NAVY));
      add(sub,txt("المباريات والترتيب عند توفر البيانات",11,false,MUTED));wt(c,sub,1);
      c.addView(txt("‹",22,true,ORANGE));c.setOnClickListener(v->{leaguePage=id;leagueTab=0;render();});
      card(page,c);
    }
  }
  void back(String label,Runnable action){
    TextView b=txt("›  "+label,14,true,ORANGE);b.setPadding(0,0,0,dp(15));
    b.setOnClickListener(v->action.run());add(page,b);
  }
  void leagueDetails(){
    back("البطولات",()->{leaguePage=null;tab=2;render();});toolbar("البطولات");
    LinearLayout hero=col();hero.setGravity(Gravity.CENTER);
    TextView symbol=leagueEmblem(leaguePage,60);
    symbol.setGravity(Gravity.CENTER);add(hero,symbol);
    TextView name=txt(leagueName(leaguePage),21,true,NAVY);name.setGravity(Gravity.CENTER);add(hero,name);
    card(page,hero);
    LinearLayout r=row();wt(r,pill("المباريات",leagueTab==0,()->{leagueTab=0;render();}),1);
    wt(r,pill("الترتيب",leagueTab==1,()->{leagueTab=1;render();}),1);add(page,r);gap(page,14);
    if(leagueTab==0){
      JSONArray games=list("matches");int n=0;LocalDate last=null;
      for(int i=0;i<games.length();i++){
        JSONObject m=at(games,i);if(!leaguePage.equals(m.optString("competition_id")))continue;
        LocalDate d=local(m.optString("kickoff"));if(d==null)continue;
        if(!d.equals(last)){add(page,txt(date(d),14,true,NAVY));gap(page,10);last=d;}
        matchCard(page,m,false);n++;
      }
      if(n==0)blank("لا تتوفر مباريات منشورة لهذه البطولة حالياً.");
    }else standings();
  }
  void standings(){
    JSONObject all=data.optJSONObject("standings");
    JSONArray a=all==null?null:all.optJSONArray(leaguePage);
    if(a==null||a.length()==0){blank("الترتيب غير متاح من المصدر لهذه البطولة. لا نعرض ترتيباً تخمينياً.");return;}
    String updated=data.optString("standings_updated_at",data.optString("generated_at",""));
    if(!updated.isEmpty()){
      try{
        long age=java.time.Duration.between(OffsetDateTime.parse(updated).toInstant(),java.time.Instant.now()).toHours();
        if(age>3)message("بيانات الترتيب منذ "+age+" ساعة؛ قد تكون النتائج الأخيرة غير منعكسة بعد.");
      }catch(Exception ignored){}
    }
    LinearLayout head=row();wt(head,txt("الفريق",12,true,MUTED),18);
    for(String x:new String[]{"لعب","ف","ت","خ","ن"}){TextView t=txt(x,11,true,MUTED);t.setGravity(Gravity.CENTER);wt(head,t,4);}
    add(page,head);gap(page,7);
    for(int i=0;i<a.length();i++){
      JSONObject team=at(a,i);LinearLayout r=row();
      String name=team.optString("team");
      wt(r,txt(team.optInt("rank",i+1)+". "+team(name),12,i<3,NAVY),18);
      for(String key:new String[]{"played","wins","draws","losses","points"}){
        TextView t=txt(team.has(key)?""+team.optInt(key):"—",12,key.equals("points"),
            key.equals("points")?ORANGE:NAVY);t.setGravity(Gravity.CENTER);wt(r,t,4);
      }
      r.setOnClickListener(v->{teamPage=name;render();});card(page,r);
    }
  }
  void matchPage(){
    back("المباريات",()->{match=null;render();});toolbar(leagueName(match.optString("competition_id")));
    LinearLayout hero=col();hero.setGravity(Gravity.CENTER);hero.setPadding(dp(16),dp(23),dp(16),dp(23));
    hero.setBackground(gradient(Color.rgb(43,61,84),Color.rgb(44,91,97),24));
    TextView teams=txt(team(match.optString("home"))+"  ×  "+team(match.optString("away")),17,true,Color.WHITE);
    teams.setGravity(Gravity.CENTER);add(hero,teams);gap(hero,12);
    TextView sc=txt(score(match),35,true,Color.WHITE);sc.setGravity(Gravity.CENTER);add(hero,sc);gap(hero,9);
    TextView st=txt(status(match.optString("status"))+" • "+date(local(match.optString("kickoff"))),12,false,Color.WHITE);
    st.setGravity(Gravity.CENTER);add(hero,st);add(page,hero);gap(page,17);
    LinearLayout r=row();String[] labels={"الملخص","الأحداث","الإحصاءات","التشكيلة"};
    for(int i=0;i<labels.length;i++){final int n=i;wt(r,pill(labels[i],detailTab==i,()->{detailTab=n;render();}),1);}
    add(page,r);gap(page,16);
    if(detailTab==0){
      detail("الموعد",time(match.optString("kickoff"))+" بتوقيت بغداد");
      detail("البطولة",leagueName(match.optString("competition_id")));
      detail("الحالة",status(match.optString("status")));
      detail("المصدر",match.optString("provider","غير محدد"));
      LinearLayout follows=row();
      String h=match.optString("home"),a=match.optString("away");
      wt(follows,pill("☆ "+team(h),following.contains(h),()->toggle(h)),1);
      wt(follows,pill("☆ "+team(a),following.contains(a),()->toggle(a)),1);
      add(page,follows);gap(page,13);
      String link=match.optString("source_url");
      if(link.startsWith("https://"))add(page,pill("رابط المصدر الرسمي ↗",false,()->open(link)));
    }else if(detailTab==1){
      JSONArray events=match.optJSONArray("events");
      if(events==null||events.length()==0)blank("أحداث المباراة غير متاحة حالياً. تُعرض الأهداف والبطاقات عند وصولها من المزود.");
      else for(int i=0;i<events.length();i++){
        JSONObject e=at(events,i);
        String type=e.optString("type","");
        String symbol=type.equals("Goal")?"⚽":type.equals("Card")?"▣":type.equals("subst")?"↔":"•";
        String who=e.optString("player","");
        String text=symbol+" "+e.optString("minute","?")+"'  "+team(e.optString("team",""));
        if(!who.isEmpty())text+=" — "+who;
        String detail=e.optString("detail","");
        if(!detail.isEmpty())text+=" ("+detail+")";
        LinearLayout row=col();
        add(row,txt(text,13,false,NAVY));
        card(page,row);
      }
    }else if(detailTab==2){
      JSONObject stats=match.optJSONObject("statistics");
      if(stats==null||stats.length()==0)blank("إحصاءات المباراة غير متوفرة لدى المزود الحالي.");
      else{
        Iterator<String> keys=stats.keys();
        while(keys.hasNext()){String k=keys.next();detail(k,stats.optString(k));}
      }
    }else{
      JSONArray players=match.optJSONArray("lineups");
      if(players==null||players.length()==0)blank("التشكيلات لم تتوفر بعد من المصدر.");
      else for(int i=0;i<players.length();i++)detail("اللاعب "+(i+1),players.optString(i));
    }
  }
  void detail(String k,String v){
    LinearLayout r=row();wt(r,txt(k,14,true,NAVY),1);
    TextView value=txt(v,13,false,MUTED);value.setGravity(Gravity.END);wt(r,value,2);card(page,r);
  }
  void teamDetails(){
    back("العودة",()->{teamPage=null;render();});toolbar("الفريق");
    LinearLayout hero=col();hero.setGravity(Gravity.CENTER);
    TextView e=txt("⚽",26,true,ORANGE);e.setGravity(Gravity.CENTER);add(hero,e);
    TextView t=txt(team(teamPage),21,true,NAVY);t.setGravity(Gravity.CENTER);add(hero,t);card(page,hero);
    add(page,pill(following.contains(teamPage)?"★ إلغاء المتابعة":"☆ متابعة الفريق",
        following.contains(teamPage),()->toggle(teamPage)));
    gap(page,16);heading("مباريات الفريق",null,null);
    int count=0;JSONArray a=list("matches");
    for(int i=0;i<a.length();i++){
      JSONObject m=at(a,i);
      if(teamPage.equals(m.optString("home"))||teamPage.equals(m.optString("away"))){
        matchCard(page,m,true);count++;
      }
    }
    if(count==0)blank("لا توجد مباريات لهذا الفريق ضمن نافذة البيانات.");
  }
  void favorites(){
    toolbar("المتابعة");heading("الفرق المتابعة",null,null);
    if(following.isEmpty())blank("اختر فرقك المفضلة من تفاصيل المباريات أو جدول الترتيب.");
    else for(String name:new TreeSet<>(following)){
      LinearLayout c=row();wt(c,txt("★  "+team(name),16,true,NAVY),1);
      c.addView(txt("عرض  ‹",13,true,ORANGE));
      c.setOnClickListener(v->{teamPage=name;render();});card(page,c);
    }
  }
  void settings(){
    toolbar("الإعدادات");heading("حول التطبيق",null,null);
    LinearLayout c=col();add(c,txt("WorldPulse Football — Android 2.0",17,true,NAVY));gap(c,9);
    add(c,txt("البرتقالي والنيلي • تصميم أصلي لعشاق كرة القدم",13,false,MUTED));gap(c,12);
    add(c,txt("7 بطولات. المواعيد والنتائج حقيقية عند توفرها. لا يتم اختلاق الترتيب أو الإحصاءات المفقودة.",13,false,NAVY));gap(c,11);
    add(c,txt("نتائج المباريات: تحديث خادم مجدول كل 5 دقائق تقريباً، وتحقق من الهاتف أثناء فتح التطبيق كل دقيقة. الجدولة قد تتأخر؛ لا يوجد ضمان لحظي أو تنبيهات أثناء إغلاق التطبيق.",12,false,MUTED));
    gap(c,10);
    add(c,txt("الألوان: #2B3D54 · #2C5B61 · #247065 · #60A65F · #FFEC97. الوضع الداكن يعتمد تلقائياً على إعداد الهاتف.",12,false,MUTED));
    gap(c,10);
    add(c,txt("لا تُحفظ صور أو ملفات نتائج على الهاتف؛ أسماء الفرق المتابعة فقط.",12,false,MUTED));card(page,c);
    add(page,pill(loading?"جارٍ التحديث...":"↻ تحديث المباريات",false,()->refresh()));gap(page,13);
    add(page,pill("المشروع على GitHub ↗",false,()->open("https://github.com/AbbasSabah97/Sport-News")));
  }
  void toggle(String s){
    if(s.isEmpty())return;
    if(following.contains(s))following.remove(s);else if(following.size()<60)following.add(s);
    prefs.edit().putStringSet("teams",new HashSet<>(following)).apply();render();
  }
  void open(String url){
    if(url==null||!url.startsWith("https://"))return;
    try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}
    catch(Exception e){Toast.makeText(this,"تعذر فتح الرابط",Toast.LENGTH_SHORT).show();}
  }
  void refresh(){
    if(loading)return;loading=true;
    client.fetch(new FeedClient.Callback(){
      @Override public void loaded(JSONObject response){
        runOnUiThread(()->{
          data=response;online=true;error=null;loading=false;
          lastScorePoll=System.currentTimeMillis();render();
        });
      }
      @Override public void failed(String msg){
        runOnUiThread(()->{error=msg;loading=false;render();});
      }
    });
  }
  private void refreshScores(){
    lastScorePoll=System.currentTimeMillis();
    client.fetchScores(new FeedClient.Callback(){
      @Override public void loaded(JSONObject fresh){
        runOnUiThread(()->{
          String oldTime=data.optString("sports_updated_at","");
          String newTime=fresh.optString("generated_at","");
          if(!newTime.equals(oldTime) && fresh.has("matches")){
            int previousY=activeScroll==null?0:activeScroll.getScrollY();
            data=FeedClient.mergeSports(data,fresh);
            if(foreground){
              render();
              if(activeScroll!=null)activeScroll.post(()->activeScroll.scrollTo(0,previousY));
            }
          }
        });
      }
      @Override public void failed(String message){
        // Retain last known schedule; the visible freshness indicator explains delays.
      }
    });
  }
  @Override protected void onResume(){
    super.onResume();
    foreground=true;
    liveHandler.removeCallbacks(liveTicker);
    liveHandler.postDelayed(liveTicker,60000);
  }
  @Override protected void onPause(){
    foreground=false;
    liveHandler.removeCallbacks(liveTicker);
    super.onPause();
  }
  @Override public void onBackPressed(){
    if(match!=null){match=null;render();}
    else if(teamPage!=null){teamPage=null;render();}
    else if(leaguePage!=null){leaguePage=null;tab=2;render();}
    else if(tab!=0){tab=0;render();}
    else super.onBackPressed();
  }
  @Override protected void onDestroy(){
    liveHandler.removeCallbacks(liveTicker);
    client.close();super.onDestroy();
  }
}
