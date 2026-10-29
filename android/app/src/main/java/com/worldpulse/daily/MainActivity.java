package com.worldpulse.daily;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

public class MainActivity extends Activity {
    private static final int PAPER = Color.rgb(248,242,230);
    private static final int CREAM = Color.rgb(238,227,209);
    private static final int WALNUT = Color.rgb(76,45,31);
    private static final int LIGHT_WALNUT = Color.rgb(119,82,59);
    private static final int RULE = Color.rgb(202,179,149);
    private static final int ACCENT = Color.rgb(106,48,34);
    private static final ZoneId BAGHDAD = ZoneId.of("Asia/Baghdad");
    private static final String[] TABS = {"الرئيسية","الأخبار","المباريات","التقرير","المزيد"};
    private static final String[] CATEGORIES = {"الكل","العالم","سياسة","اقتصاد","تقنية","الذكاء الاصطناعي","رياضة"};

    private final FeedClient client = new FeedClient();
    private JSONObject feed = new JSONObject();
    private SharedPreferences preferences;
    private final Set<String> favorites = new HashSet<>();
    private LinearLayout container;
    private LinearLayout bottomBar;
    private LinearLayout articleList;
    private LinearLayout chips;
    private TextToSpeech speaker;
    private int tab = 0;
    private String category = "الكل";
    private String competition = "all";
    private String search = "";
    private JSONObject openedArticle = null;
    private boolean favoritesPage = false;
    private boolean loading = false;
    private String error = null;
    private boolean dataReady = false;
    private long lastRefresh = 0;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            getWindow().getDecorView().setForceDarkAllowed(false);
        }
        getWindow().setStatusBarColor(PAPER);
        getWindow().setNavigationBarColor(PAPER);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        preferences = getSharedPreferences("worldpulse_prefs", MODE_PRIVATE);
        favorites.addAll(preferences.getStringSet("saved_ids", new HashSet<>()));
        try {
            byte[] raw;
            try (java.io.InputStream in = getAssets().open("preview-feed.json");
                 java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
                byte[] chunk = new byte[2048];
                int length;
                while ((length = in.read(chunk)) != -1) {
                    if (out.size() + length > 30_000) break;
                    out.write(chunk, 0, length);
                }
                raw = out.toByteArray();
            }
            feed = new JSONObject(new String(raw, java.nio.charset.StandardCharsets.UTF_8));
        } catch (Exception ignored) { }
        render();
        refresh(false);
    }

    private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    private GradientDrawable background(int color, float radius, int outline) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        if (outline != 0) d.setStroke(dp(1), outline);
        return d;
    }
    private LinearLayout column() {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        return c;
    }
    private LinearLayout row() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        return r;
    }
    private TextView text(String value, int size, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(WALNUT);
        t.setTextDirection(View.TEXT_DIRECTION_FIRST_STRONG);
        t.setGravity(Gravity.CENTER_VERTICAL);
        t.setTypeface(Typeface.create("serif",bold?Typeface.BOLD:Typeface.NORMAL));
        t.setIncludeFontPadding(true);
        return t;
    }
    private TextView muted(String value, int size) {
        TextView t=text(value,size,false);
        t.setTextColor(LIGHT_WALNUT);
        return t;
    }
    private void add(LinearLayout host, View child) {
        host.addView(child, new LinearLayout.LayoutParams(-1,-2));
    }
    private void gap(LinearLayout host, int height) {
        View v=new View(this);
        host.addView(v,new LinearLayout.LayoutParams(1,dp(height)));
    }
    private void rule(LinearLayout host) {
        View v = new View(this);
        v.setBackgroundColor(RULE);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(1));
        p.topMargin=dp(9);
        p.bottomMargin=dp(9);
        host.addView(v,p);
    }
    private void space(LinearLayout host, View view, float weight) {
        host.addView(view, new LinearLayout.LayoutParams(0,-2,weight));
    }
    private void card(LinearLayout parent, View item) {
        LinearLayout wrap=column();
        wrap.setPadding(dp(13),dp(12),dp(13),dp(12));
        wrap.setBackground(background(PAPER,3,RULE));
        add(wrap,item);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);
        lp.bottomMargin=dp(10);
        parent.addView(wrap,lp);
    }
    private TextView button(String label, boolean selected, Runnable action) {
        TextView b=text(label,14,selected);
        b.setTextColor(selected?PAPER:WALNUT);
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(13),dp(9),dp(13),dp(9));
        b.setBackground(background(selected?WALNUT:CREAM,5,selected?0:RULE));
        b.setOnClickListener(v->action.run());
        return b;
    }
    private void render() {
        LinearLayout root=column();
        root.setBackgroundColor(PAPER);
        root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        setContentView(root);
        FrameLayout bodyFrame=new FrameLayout(this);
        root.addView(bodyFrame,new LinearLayout.LayoutParams(-1,0,1));
        ScrollView scroller=new ScrollView(this);
        scroller.setFillViewport(true);
        scroller.setVerticalScrollBarEnabled(false);
        bodyFrame.addView(scroller,new FrameLayout.LayoutParams(-1,-1));
        container=column();
        container.setPadding(dp(17),dp(14),dp(17),dp(24));
        scroller.addView(container,new ScrollView.LayoutParams(-1,-2));
        if (openedArticle!=null) drawDetail();
        else if (favoritesPage) drawFavorites();
        else switch (tab) {
            case 0: drawHome();break;
            case 1: drawNews();break;
            case 2: drawMatches();break;
            case 3: drawReport();break;
            default: drawMore();
        }
        bottomBar=row();
        bottomBar.setPadding(dp(6),dp(6),dp(6),dp(8));
        bottomBar.setBackground(background(CREAM,0,0));
        View line = new View(this);
        line.setBackgroundColor(RULE);
        root.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));
        for (int i=0;i<TABS.length;i++) {
            final int index=i;
            LinearLayout tabView=column();
            tabView.setGravity(Gravity.CENTER);
            String ornament=tab==i&&!favoritesPage&&openedArticle==null?"◆":"◇";
            TextView sym=text(ornament,12,false);
            sym.setTextColor(tab==i?ACCENT:LIGHT_WALNUT);
            sym.setGravity(Gravity.CENTER);
            add(tabView,sym);
            TextView label=text(TABS[i],12,tab==i);
            label.setTextColor(tab==i?ACCENT:LIGHT_WALNUT);
            label.setGravity(Gravity.CENTER);
            add(tabView,label);
            tabView.setOnClickListener(v->{
                tab=index; openedArticle=null; favoritesPage=false;
                if(tab==1 && category==null)category="الكل";
                render();
            });
            bottomBar.addView(tabView,new LinearLayout.LayoutParams(0,dp(53),1));
        }
        add(root,bottomBar);
    }
    private void masthead(String section) {
        LinearLayout top=row();
        TextView mark=muted("✦ صحيفة يومية ✦",12);
        space(top,mark,1);
        TextView update=muted("بتوقيت بغداد",11);
        update.setGravity(Gravity.END);
        space(top,update,1);
        add(container,top);
        rule(container);
        TextView logo=text("WorldPulse",34,true);
        logo.setTypeface(Typeface.create("serif",Typeface.BOLD));
        logo.setGravity(Gravity.CENTER);
        add(container,logo);
        TextView sub=text("نبض العالم  •  أخبار ورياضة",13,false);
        sub.setGravity(Gravity.CENTER);
        add(container,sub);
        gap(container,4);
        TextView edition=muted("العدد الرقمي  |  " + getDate() + "  |  " + section,12);
        edition.setGravity(Gravity.CENTER);
        add(container,edition);
        rule(container);
    }
    private String getDate() {
        return java.time.LocalDate.now(BAGHDAD)
                .format(DateTimeFormatter.ofPattern("dd / MM / uuuu", Locale.ENGLISH));
    }
    private void heading(String title) {
        gap(container,8);
        TextView h=text("—  " + title + "  —",20,true);
        h.setGravity(Gravity.CENTER);
        add(container,h);
        rule(container);
    }
    private void banner() {
        String newsStatus=feed.optString("news_status","");
        if ("demo".equals(newsStatus)) {
            note("معاينة تجريبية — الأخبار والمباريات المعروضة أمثلة وليست بيانات حقيقية.");
        } else if (!dataReady || !"ok".equals(newsStatus)) {
            note("تعذر تحديث بعض الأخبار؛ تأكد من الاتصال بالإنترنت.");
        }
        if(error!=null)note(error);
    }
    private void note(String message) {
        TextView note=muted(message,13);
        note.setPadding(dp(12),dp(11),dp(12),dp(11));
        note.setBackground(background(CREAM,4,RULE));
        add(container,note);
        gap(container,10);
    }
    private JSONArray items(String name) {return feed.optJSONArray(name)==null?new JSONArray():feed.optJSONArray(name);}
    private boolean isArabic(String value) {
        if (value==null)return false;
        int arabic=0,latin=0;
        for(int i=0;i<value.length();i++){
            char c=value.charAt(i);
            if (c>=0x0600 && c<=0x06FF)arabic++;
            else if ((c>='A' && c<='Z')||(c>='a' && c<='z'))latin++;
        }
        return arabic>=5 && arabic>=latin;
    }
    private JSONObject at(JSONArray data,int i) {return data.optJSONObject(i)==null?new JSONObject():data.optJSONObject(i);}
    private void storyRow(LinearLayout host,JSONObject item,int index,boolean summary) {
        String title=item.optString("title","");
        if(!isArabic(title))return;
        LinearLayout wrapper=column();
        LinearLayout line=row();
        TextView number=text(String.format(Locale.US,"%02d",index),12,true);
        number.setTextColor(ACCENT);
        number.setGravity(Gravity.TOP);
        number.setWidth(dp(32));
        line.addView(number,new LinearLayout.LayoutParams(dp(36),-2));
        TextView titleText=text(title,summary?18:16,true);
        titleText.setLineSpacing(dp(3),1);
        line.addView(titleText,new LinearLayout.LayoutParams(0,-2,1));
        add(wrapper,line);
        String synopsis=item.optString("summary","");
        if(summary&&!synopsis.isEmpty()){
            gap(wrapper,6);
            TextView lead=muted(synopsis,14);
            lead.setLineSpacing(dp(2),1);
            add(wrapper,lead);
        }
        gap(wrapper,6);
        TextView source=muted(item.optString("source","")+
                "    •    "+item.optString("category","")+"    •    "+stamp(item.optString("published_at","")),11);
        add(wrapper,source);
        wrapper.setPadding(dp(2),dp(9),dp(2),dp(9));
        wrapper.setOnClickListener(v->{openedArticle=item;render();});
        add(host,wrapper);
        rule(host);
    }
    private String stamp(String value) {
        try {
            return OffsetDateTime.parse(value).atZoneSameInstant(BAGHDAD)
                    .format(DateTimeFormatter.ofPattern("dd/MM  HH:mm",Locale.ENGLISH));
        } catch(Exception ex) { return "—"; }
    }
    private void drawHome() {
        masthead("الصفحة الرئيسية");
        banner();
        TextView kicker=muted("العناوين البارزة  /  آخر تحديث "+stamp(feed.optString("generated_at","")),12);
        add(container,kicker);
        JSONArray news=items("news");
        if(news.length()==0)note("لا توجد أخبار منشورة حالياً.");
        else {
            int printed=0;
            for(int i=0;i<news.length() && printed<7;i++){
                JSONObject item=at(news,i);
                if(!isArabic(item.optString("title","")))continue;
                storyRow(container,item,++printed,printed==1);
            }
            if(printed==0)note("لم تتوفر عناوين عربية؛ أعد تحديث البيانات.");
        }
        heading("آخر أخبار الذكاء الاصطناعي");
        int aiCount=0;
        for(int i=0;i<news.length() && aiCount<4;i++){
            JSONObject item=at(news,i);
            if("الذكاء الاصطناعي".equals(item.optString("category")) && isArabic(item.optString("title",""))){
                storyRow(container,item,++aiCount,false);
            }
        }
        if(aiCount==0)note("لا تتوفر حالياً أخبار موثوقة بالعربية في هذا القسم.");
        add(container,button("عرض قسم الذكاء الاصطناعي",false,()->{
            tab=1;category="الذكاء الاصطناعي";search="";render();
        }));
        heading("مباريات اليوم");
        JSONArray games=items("matches");
        if(games.length()==0)note("لا توجد مباريات حالياً أو لم يُضبط مصدر النتائج.");
        else for(int i=0;i<Math.min(3,games.length());i++)drawMatch(container,at(games,i));
    }
    private void drawNews() {
        masthead("الأقسام");
        banner();
        EditText input=new EditText(this);
        input.setSingleLine(true);
        input.setTextSize(15);
        input.setTextColor(WALNUT);
        input.setHintTextColor(LIGHT_WALNUT);
        input.setHint("ابحث في عناوين الأخبار...");
        input.setPadding(dp(12),dp(9),dp(12),dp(9));
        input.setBackground(background(CREAM,4,RULE));
        input.setText(search);
        add(container,input);
        gap(container,12);
        HorizontalScrollView scroll=new HorizontalScrollView(this);
        scroll.setHorizontalScrollBarEnabled(false);
        chips=row();
        scroll.addView(chips);
        add(container,scroll);
        renderCategoryChips();
        heading("آخر الأخبار");
        articleList=column();
        add(container,articleList);
        updateArticles();
        input.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){}
            @Override public void onTextChanged(CharSequence s,int start,int before,int count){
                search=s.toString().trim();updateArticles();
            }
            @Override public void afterTextChanged(Editable e){}
        });
    }
    private void renderCategoryChips() {
        chips.removeAllViews();
        for(String c:CATEGORIES) {
            TextView b=button(c,c.equals(category),()->{
                category=c;renderCategoryChips();updateArticles();
            });
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2);
            p.setMargins(dp(3),0,dp(3),0);
            chips.addView(b,p);
        }
    }
    private void updateArticles() {
        if(articleList==null)return;
        articleList.removeAllViews();
        JSONArray news=items("news");
        int count=0;
        for(int i=0;i<news.length();i++) {
            JSONObject item=at(news,i);
            if(!isArabic(item.optString("title","")))continue;
            if(!category.equals("الكل")&&!category.equals(item.optString("category")))continue;
            String query=(item.optString("title")+" "+item.optString("summary")+" "+item.optString("source"))
                    .toLowerCase(Locale.ROOT);
            if(!query.contains(search.toLowerCase(Locale.ROOT)))continue;
            storyRow(articleList,item,++count,false);
        }
        if(count==0)add(articleList,muted("لا توجد نتائج لهذا التصنيف أو البحث.",14));
    }
    private void drawDetail() {
        TextView back=button("‹  العودة إلى الأخبار",false,()->{openedArticle=null;render();});
        add(container,back);
        masthead("تفاصيل الخبر");
        TextView category=muted(openedArticle.optString("category","العالم"),12);
        add(container,category);
        gap(container,10);
        TextView title=text(openedArticle.optString("title",""),26,true);
        title.setLineSpacing(dp(5),1);
        add(container,title);
        gap(container,10);
        add(container,muted(openedArticle.optString("source","")+"   •   "+
                stamp(openedArticle.optString("published_at","")),12));
        rule(container);
        TextView summary=text(openedArticle.optString("summary","افتح المصدر لقراءة الخبر كاملاً."),17,false);
        summary.setLineSpacing(dp(6),1);
        add(container,summary);
        gap(container,20);
        final String id=openedArticle.optString("id","");
        add(container,button(favorites.contains(id)?"★ إزالة من المفضلة":"☆ حفظ الخبر",false,()->{
            if(favorites.contains(id))favorites.remove(id);
            else if(favorites.size()<120)favorites.add(id);
            preferences.edit().putStringSet("saved_ids",new HashSet<>(favorites)).apply();
            render();
        }));
        gap(container,10);
        String link=openedArticle.optString("url","");
        if(link.startsWith("https://")) {
            add(container,button("قراءة المقال في موقع المصدر ↗",true,()->openLink(link)));
            gap(container,10);
            add(container,button("مشاركة رابط الخبر",false,()->{
                Intent send=new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_TEXT,link);
                startActivity(Intent.createChooser(send,"مشاركة الخبر"));
            }));
        }
        gap(container,12);
        add(container,muted("يعرض التطبيق نصوصاً قصيرة فقط. وقد يحتوي موقع المصدر الخارجي على صور.",12));
    }
    private void openLink(String url) {
        try {
            Intent intent=new Intent(Intent.ACTION_VIEW,Uri.parse(url));
            startActivity(intent);
        } catch(Exception e) {Toast.makeText(this,"لا يوجد متصفح متاح",Toast.LENGTH_SHORT).show();}
    }
    private void drawMatches() {
        masthead("الرياضة");
        banner();
        heading("مباريات اليوم");
        add(container,muted("التوقيت المحلي: بغداد   |   "+feed.optString("local_date",getDate()),13));
        gap(container,10);
        HorizontalScrollView scroll=new HorizontalScrollView(this);
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout filter=row();
        scroll.addView(filter);
        add(container,scroll);
        JSONArray leagues=items("competitions");
        addChip(filter,"all","كل البطولات");
        for(int i=0;i<leagues.length();i++) {
            JSONObject lg=at(leagues,i);
            addChip(filter,lg.optString("id"),lg.optString("name"));
        }
        gap(container,15);
        JSONArray matches=items("matches");
        if("not_configured".equals(feed.optString("sports_status")))note("لم تُفعّل خدمة المباريات بعد؛ يُمكن تفعيل المصدر الأساسي من GitHub.");
        if("partial".equals(feed.optString("sports_status")))note(feed.optString("sports_error","تغطية جزئية للمباريات اليوم."));
        if("error".equals(feed.optString("sports_status")))note("تعذر الوصول إلى مصادر بيانات المباريات.");
        int visible=0;
        for(int i=0;i<matches.length();i++) {
            JSONObject m=at(matches,i);
            if(!competition.equals("all")&&!competition.equals(m.optString("competition_id")))continue;
            drawMatch(container,m);visible++;
        }
        if(visible==0)note("لا توجد مباريات معلنة لهذا اليوم في المصدر المتاح؛ قد يكون الدوري متوقفاً أو تغطيته غير مكتملة.");
        add(container,muted("قد تتأخر تحديثات النتائج؛ لا يُعدّ هذا بثاً لحظياً.",12));
    }
    private void addChip(LinearLayout holder,String id,String name) {
        TextView b=button(name,id.equals(competition),()->{competition=id;render();});
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2);
        p.leftMargin=dp(4);p.rightMargin=dp(4);
        holder.addView(b,p);
    }
    private void drawMatch(LinearLayout parent,JSONObject match) {
        LinearLayout section=column();
        TextView league=muted("⚽  "+match.optString("league","بطولة"),12);
        add(section,league);
        rule(section);
        TextView teams=text(match.optString("home","")+"    ×    "+match.optString("away",""),17,true);
        teams.setGravity(Gravity.CENTER);
        teams.setMaxLines(3);
        add(section,teams);
        gap(section,7);
        boolean hasScore=!match.isNull("home_goals")&&!match.isNull("away_goals");
        String status=match.optString("status","NS");
        String score=hasScore ? match.optInt("home_goals")+" : "+match.optInt("away_goals") : "VS";
        TextView time=muted(score+"   |   "+stamp(match.optString("kickoff",""))+"   |   "+status,13);
        time.setGravity(Gravity.CENTER);
        add(section,time);
        card(parent,section);
    }
    private void drawReport() {
        masthead("التقرير الساعي");
        banner();
        heading("موجز الساعة");
        TextView updated=muted("آخر تحديث: "+stamp(feed.optString("generated_at","")),13);
        updated.setGravity(Gravity.CENTER);
        add(container,updated);
        gap(container,12);
        JSONArray digest=items("digest");
        add(container,button("▶ استمع إلى العناوين",false,()->readReport(digest)));
        gap(container,12);
        for(int i=0;i<digest.length();i++) {
            JSONObject story=at(digest,i);
            if(!isArabic(story.optString("headline","")))continue;
            LinearLayout line=column();
            add(line,text(String.format(Locale.US,"%02d",i+1)+"   "+story.optString("headline",""),16,true));
            gap(line,5);
            add(line,muted(story.optString("source","")+"  •  "+story.optString("category",""),12));
            String link=story.optString("url","");
            if(link.startsWith("https://"))line.setOnClickListener(v->openLink(link));
            card(container,line);
        }
        if(digest.length()==0)note("لا تتوفر عناوين عربية للتقرير في الوقت الحالي.");
        add(container,muted("هذه خلاصة للعناوين المنشورة لدى المصادر الأصلية، وليست تحليلاً مستقلاً للأحداث.",12));
    }
    private void readReport(JSONArray digest) {
        StringBuilder script=new StringBuilder();
        for(int i=0;i<digest.length();i++)script.append(at(digest,i).optString("headline")).append(". ");
        if(script.length()==0)return;
        if(speaker!=null) {speaker.stop();speaker.shutdown();}
        speaker=new TextToSpeech(this,status->{
            if(status==TextToSpeech.SUCCESS && speaker!=null) {
                speaker.setLanguage(new Locale("ar"));
                speaker.speak(script.toString(),TextToSpeech.QUEUE_FLUSH,null,"worldpulse-digest");
            }else Toast.makeText(this,"تعذر تشغيل القراءة الصوتية",Toast.LENGTH_SHORT).show();
        });
    }
    private void drawFavorites() {
        masthead("الأخبار المحفوظة");
        int count=0;
        JSONArray articles=items("news");
        for(int i=0;i<articles.length();i++) {
            JSONObject article=at(articles,i);
            if(!favorites.contains(article.optString("id")) || !isArabic(article.optString("title","")))continue;
            storyRow(container,article,++count,false);
        }
        if(count==0)note("لا توجد عناوين محفوظة ضمن الأخبار الحالية. يتم حفظ معرّفات المفضلة فقط لتقليل التخزين.");
    }
    private void drawMore() {
        masthead("الإعدادات");
        banner();
        heading("النسخة الورقية الرقمية");
        add(container,button("↻ تحديث الأخبار والمباريات",true,()->refresh(true)));
        gap(container,12);
        add(container,button("☆ الأخبار المفضلة ("+favorites.size()+")",false,()->{
            favoritesPage=true;render();
        }));
        gap(container,12);
        LinearLayout info=column();
        add(info,text("WorldPulse — Android 1.1",17,true));
        gap(info,10);
        add(info,muted("هوية صحيفة كلاسيكية • ورق عاجي • حبر جوزي",14));
        gap(info,8);
        add(info,muted("• لا صور أو خلفيات صور داخل التطبيق.\n• لا تنزيل ملفات أخبار إلى التخزين.\n• تحفظ الإعدادات ومعرّفات المفضلة فقط.\n• تحديث الأخبار يتم على GitHub وليس على الهاتف.\n• يحتاج الإنترنت لجلب الأخبار الحقيقية.",14));
        gap(info,8);
        add(info,muted("آخر تحديث: "+stamp(feed.optString("generated_at","")),12));
        card(container,info);
        add(container,button("فتح المشروع على GitHub",false,()->
            openLink("https://github.com/AbbasSabah97/Sport-News")));
    }
    private void refresh(boolean force) {
        long now=System.currentTimeMillis();
        if(loading || (!force && now-lastRefresh<240_000))return;
        loading=true;
        lastRefresh=now;
        if(force)Toast.makeText(this,"جار تحديث البيانات...",Toast.LENGTH_SHORT).show();
        client.fetch(new FeedClient.Callback() {
            @Override public void loaded(JSONObject result) {
                runOnUiThread(()->{
                    loading=false;error=null;dataReady=true;
                    feed=result;
                    openedArticle=null;
                    render();
                });
            }
            @Override public void failed(String message) {
                runOnUiThread(()->{
                    loading=false;error=message;dataReady=false;
                    render();
                });
            }
        });
    }
    @Override public void onBackPressed() {
        if(openedArticle!=null) {openedArticle=null;render();}
        else if(favoritesPage){favoritesPage=false;render();}
        else if(tab!=0){tab=0;render();}
        else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        client.close();
        if(speaker!=null){speaker.stop();speaker.shutdown();}
        super.onDestroy();
    }
}
