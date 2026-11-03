package com.worldpulse.daily;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Separate hourly editorial feed and more frequently refreshed football feed. */
public final class FeedClient {
    public interface Callback {
        void loaded(JSONObject json);
        void failed(String message);
    }
    private static final String ROOT =
        "https://raw.githubusercontent.com/AbbasSabah97/Sport-News/main/docs/";
    private static final int MAX_BYTES=350_000;
    private final ExecutorService executor=Executors.newSingleThreadExecutor();

    private JSONObject read(String endpoint) throws Exception {
        HttpURLConnection connection=null;
        try {
            // Timestamp prevents stale intermediary caches, never stores response on disk.
            URL url=new URL(ROOT+endpoint+"?t="+(System.currentTimeMillis()/30000));
            connection=(HttpURLConnection)url.openConnection();
            connection.setConnectTimeout(9000);
            connection.setReadTimeout(12000);
            connection.setUseCaches(false);
            connection.setRequestProperty("Cache-Control","no-cache, no-store");
            connection.setRequestProperty("Accept","application/json");
            if(connection.getResponseCode()!=200)throw new IllegalStateException("HTTP "+connection.getResponseCode());
            try(InputStream input=connection.getInputStream();ByteArrayOutputStream buffer=new ByteArrayOutputStream()) {
                byte[] block=new byte[4096];
                int n;
                while((n=input.read(block))!=-1){
                    if(buffer.size()+n>MAX_BYTES)throw new IllegalStateException("Feed too large");
                    buffer.write(block,0,n);
                }
                JSONObject result=new JSONObject(buffer.toString(StandardCharsets.UTF_8.name()));
                if(result.optInt("schema_version")!=1)throw new IllegalStateException("Unexpected schema");
                return result;
            }
        }finally{
            if(connection!=null)connection.disconnect();
        }
    }

    public static JSONObject mergeSports(JSONObject base,JSONObject scores) {
        if(scores==null || scores.optInt("schema_version")!=1 || !scores.has("matches"))return base;
        try {
            base.put("matches",scores.getJSONArray("matches"));
            for(String name:new String[]{"sports_status","sports_error","sports_checked","week_start","week_end","live_count"}) {
                if(scores.has(name))base.put(name,scores.get(name));
            }
            base.put("sports_updated_at",scores.optString("generated_at",""));
            if(scores.has("source_generated_at"))
                base.put("sports_source_updated_at",scores.optString("source_generated_at",""));
        }catch(Exception ignored){}
        return base;
    }
    public void fetch(Callback callback) {
        executor.submit(()->{
            try {
                JSONObject feed=read("feed.json");
                // The newer scores feed is optional during first deployment.
                try { mergeSports(feed,read("fixtures.json")); }
                catch(Exception ignored){}
                if(!feed.has("matches"))throw new IllegalStateException("Missing matches");
                callback.loaded(feed);
            }catch(Exception e){
                callback.failed("تعذر الاتصال بالخادم؛ تحقق من اتصال الإنترنت.");
            }
        });
    }
    public void fetchScores(Callback callback) {
        executor.submit(()->{
            try {callback.loaded(read("fixtures.json"));}
            catch(Exception e){callback.failed("تعذر تحديث المباريات حالياً.");}
        });
    }
    public void close(){executor.shutdownNow();}
}
