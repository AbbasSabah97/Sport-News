package com.worldpulse.daily;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class FeedClient {
    public interface Callback {
        void loaded(JSONObject json);
        void failed(String message);
    }
    private static final String URL_FEED =
            "https://raw.githubusercontent.com/AbbasSabah97/Sport-News/main/docs/feed.json";
    private static final int LIMIT_BYTES = 300_000;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    public void fetch(Callback callback) {
        executor.submit(()->{
            HttpURLConnection connection=null;
            try {
                URL url=new URL(URL_FEED);
                connection=(HttpURLConnection)url.openConnection();
                connection.setConnectTimeout(10_000);
                connection.setReadTimeout(15_000);
                connection.setUseCaches(false);
                connection.setRequestProperty("Cache-Control","no-store");
                connection.setRequestProperty("Accept","application/json");
                if(connection.getResponseCode()!=200)throw new IllegalStateException("HTTP "+connection.getResponseCode());
                try(InputStream input=connection.getInputStream();ByteArrayOutputStream buffer=new ByteArrayOutputStream()){
                    byte[] block=new byte[4096];
                    int read;
                    while((read=input.read(block))!=-1){
                        if(buffer.size()+read>LIMIT_BYTES)throw new IllegalStateException("الموجز أكبر من الحد المسموح");
                        buffer.write(block,0,read);
                    }
                    JSONObject data=new JSONObject(buffer.toString(StandardCharsets.UTF_8.name()));
                    if(data.optInt("schema_version")!=1)throw new IllegalStateException("نسخة بيانات غير معروفة");
                    if(!data.has("news") || !data.has("matches"))throw new IllegalStateException("بيانات ناقصة");
                    callback.loaded(data);
                }
            }catch(Exception e){
                callback.failed("تعذر تحميل البيانات؛ تحقق من اتصال الإنترنت ثم أعد المحاولة.");
            }finally{
                if(connection!=null)connection.disconnect();
            }
        });
    }
    public void close(){executor.shutdownNow();}
}
