package cn.cet.learningdesk;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.PackageInfo;
import android.content.pm.Signature;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import android.util.Base64;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import androidx.core.content.FileProvider;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.net.HttpURLConnection;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.net.URL;
import java.net.URLEncoder;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

public class MainActivity extends Activity {
    private static final String TAG = "CETLearningDesk";
    private static final String RESOURCE_VERSION = BuildConfig.VERSION_NAME + "-resources-2";
    private static final String UPDATE_MANIFEST_URL = "https://github.com/sixinzheng/cet-learning-desk/releases/latest/download/android-latest.json";
    private static final long MAX_APK_BYTES = 250L * 1024L * 1024L;
    private static final int UPDATE_CONNECT_TIMEOUT_MS = 12000;
    private static final int MANIFEST_READ_TIMEOUT_MS = 45000;
    private static final int APK_READ_TIMEOUT_MS = 120000;
    private static final int UPDATE_MAX_ATTEMPTS = 3;
    private static final int UPDATE_PERMISSION_REQUEST = 4103;
    private static final int FILE_CHOOSER_REQUEST = 4101;
    private static final int AUDIO_PERMISSION_REQUEST = 4102;
    private static final int SYNC_CAMERA_PERMISSION_REQUEST = 4104;
    private static final int MAX_SYNC_PACKAGE_BYTES = 33 * 1024 * 1024;

    private final ExecutorService backendExecutor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingAudioPermission;
    private String backendBaseUrl;
    private File pendingUpdateApk;
    private TextToSpeech nativeSpeech;
    private volatile boolean nativeSpeechReady = false;
    private volatile boolean pendingSyncScan = false;
    private PairingData pendingPairing;
    private String pendingSyncTicket;
    private JSONObject pendingPeer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(48, 59, 103));
        getWindow().setNavigationBarColor(Color.rgb(245, 240, 231));
        SecureStore.init(this);
        configureWebView();
        configureNativeSpeech();
        showLoading();
        backendExecutor.execute(this::startBackend);
    }

    private void configureWebView() {
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(245, 240, 231));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " CETLearningDeskAndroid/" + BuildConfig.VERSION_NAME);
        webView.addJavascriptInterface(new NativeSpeechBridge(), "CETNativeSpeech");
        webView.addJavascriptInterface(new NativeDeviceSyncBridge(), "CETNativeSync");
        CookieManager.getInstance().setAcceptCookie(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("cetlearningdesk".equals(uri.getScheme())) {
                    handleNativeUpdateAction(view, uri);
                    return true;
                }
                String host = uri.getHost();
                if ("127.0.0.1".equals(host) || "localhost".equals(host)) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (ActivityNotFoundException ignored) {
                    showError("手机上没有可打开此链接的应用。");
                }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                    WebView view,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (fileCallback != null) {
                    fileCallback.onReceiveValue(null);
                }
                fileCallback = callback;
                try {
                    Intent intent = params.createIntent();
                    intent.setType("image/*");
                    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, false);
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException error) {
                    fileCallback.onReceiveValue(null);
                    fileCallback = null;
                    showError("手机上没有可用于拍照或选择图片的应用。");
                    return false;
                }
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                Uri origin = request.getOrigin();
                if (origin == null || !("127.0.0.1".equals(origin.getHost())
                        || "localhost".equals(origin.getHost()))) {
                    request.deny();
                    return;
                }
                boolean asksForAudio = false;
                for (String resource : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                        asksForAudio = true;
                    }
                }
                if (!asksForAudio) {
                    request.deny();
                    return;
                }
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                        == PackageManager.PERMISSION_GRANTED) {
                    request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                } else {
                    pendingAudioPermission = request;
                    requestPermissions(
                            new String[]{Manifest.permission.RECORD_AUDIO},
                            AUDIO_PERMISSION_REQUEST);
                }
            }
        });
    }

    private void configureNativeSpeech() {
        nativeSpeech = new TextToSpeech(this, status -> {
            nativeSpeechReady = status == TextToSpeech.SUCCESS;
            if (nativeSpeechReady) {
                int languageResult = nativeSpeech.setLanguage(Locale.US);
                nativeSpeechReady = languageResult != TextToSpeech.LANG_MISSING_DATA
                        && languageResult != TextToSpeech.LANG_NOT_SUPPORTED;
            }
        });
    }

    private final class NativeSpeechBridge {
        @JavascriptInterface
        public boolean speak(String text, double rate) {
            if (!nativeSpeechReady || nativeSpeech == null || text == null || text.trim().isEmpty()) {
                return false;
            }
            final String safeText = text.length() > 6000 ? text.substring(0, 6000) : text;
            final float safeRate = (float) Math.max(0.5, Math.min(1.5, rate));
            runOnUiThread(() -> {
                nativeSpeech.stop();
                nativeSpeech.setLanguage(Locale.US);
                nativeSpeech.setSpeechRate(safeRate);
                nativeSpeech.speak(safeText, TextToSpeech.QUEUE_FLUSH, null, "cet-native-speech");
            });
            return true;
        }

        @JavascriptInterface
        public void stop() {
            if (nativeSpeech != null) runOnUiThread(() -> nativeSpeech.stop());
        }
    }

    private static final class PairingData {
        final String baseUrl;
        final String token;
        final String fingerprint;
        final String sessionId;

        PairingData(String baseUrl, String token, String fingerprint, String sessionId) {
            this.baseUrl = baseUrl;
            this.token = token;
            this.fingerprint = fingerprint;
            this.sessionId = sessionId;
        }
    }

    private final class NativeDeviceSyncBridge {
        @JavascriptInterface
        public void scanPairingCode() {
            runOnUiThread(() -> {
                if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    launchSyncScanner();
                } else {
                    pendingSyncScan = true;
                    requestPermissions(new String[]{Manifest.permission.CAMERA}, SYNC_CAMERA_PERMISSION_REQUEST);
                }
            });
        }

        @JavascriptInterface
        public void inspect(String pairingCode, String localTicket) {
            backendExecutor.execute(() -> inspectPairing(pairingCode, localTicket));
        }

        @JavascriptInterface
        public void confirm() {
            backendExecutor.execute(MainActivity.this::performDeviceSync);
        }

        @JavascriptInterface
        public void cancel() {
            pendingPairing = null;
            pendingSyncTicket = null;
            pendingPeer = null;
        }
    }

    private void launchSyncScanner() {
        IntentIntegrator integrator = new IntentIntegrator(this);
        integrator.setPrompt("扫描电脑上显示的设备同步二维码");
        integrator.setBeepEnabled(false);
        integrator.setOrientationLocked(true);
        integrator.setBarcodeImageEnabled(false);
        integrator.setDesiredBarcodeFormats("QR_CODE");
        integrator.initiateScan();
    }

    private PairingData parsePairingCode(String code) throws Exception {
        String value = code == null ? "" : code.trim();
        if (value.startsWith("cet-sync:")) value = value.substring(9);
        byte[] decoded = Base64.decode(value, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
        JSONObject payload = new JSONObject(new String(decoded, StandardCharsets.UTF_8));
        if (payload.optInt("v", 0) != 1) throw new IOException("配对码版本不受支持");
        String baseUrl = payload.optString("url", "");
        String token = payload.optString("token", "");
        String fingerprint = payload.optString("fingerprint", "").toLowerCase(Locale.ROOT);
        String sessionId = payload.optString("session_id", "");
        URL url = new URL(baseUrl);
        InetAddress address = InetAddress.getByName(url.getHost());
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getPort() <= 0
                || !address.isSiteLocalAddress() || token.length() < 32
                || !fingerprint.matches("[0-9a-f]{64}") || sessionId.length() < 8) {
            throw new IOException("配对码没有指向可信的同一 Wi-Fi 私网服务");
        }
        return new PairingData(baseUrl, token, fingerprint, sessionId);
    }

    private void inspectPairing(String pairingCode, String localTicket) {
        try {
            PairingData pairing = parsePairingCode(pairingCode);
            notifyDeviceSync("inspecting", "正在验证电脑", "正在核对临时证书与一次性配对令牌。", null);
            HttpsURLConnection connection = openPinnedSyncConnection(pairing, "/sync/v1/handshake", "GET");
            JSONObject handshake;
            try {
                handshake = readJsonResponse(connection, 512 * 1024);
            } finally {
                connection.disconnect();
            }
            if (!pairing.sessionId.equals(handshake.optString("session_id"))) {
                throw new IOException("电脑返回的同步会话与二维码不一致");
            }
            pendingPairing = pairing;
            pendingSyncTicket = String.valueOf(localTicket == null ? "" : localTicket).trim();
            pendingPeer = handshake.optJSONObject("device");
            notifyDeviceSync("preview", "已安全连接电脑", "请核对设备和数据摘要后确认同步。", handshake);
        } catch (Exception error) {
            pendingPairing = null; pendingSyncTicket = null; pendingPeer = null;
            notifyDeviceSync("error", "无法连接电脑", safeErrorMessage(error), null);
        }
    }

    private void performDeviceSync() {
        PairingData pairing = pendingPairing;
        String ticket = pendingSyncTicket;
        if (pairing == null || ticket == null || ticket.length() < 20) {
            notifyDeviceSync("error", "同步确认已失效", "请重新扫描电脑上的二维码。", null);
            return;
        }
        try {
            notifyDeviceSync("exporting", "正在备份手机数据", "手机会先生成并校验同步前备份。", null);
            JSONObject localEnvelope = localSyncRequest(
                    "/api/device-sync/native-package/" + URLEncoder.encode(ticket, StandardCharsets.UTF_8.name()),
                    "GET", null);
            JSONObject localPackage = localEnvelope.getJSONObject("package");

            notifyDeviceSync("exchanging", "正在双向合并", "通过临时加密通道交换学习记录。", null);
            HttpsURLConnection exchange = openPinnedSyncConnection(pairing, "/sync/v1/exchange", "POST");
            JSONObject response;
            try {
                writeJsonBody(exchange, localPackage.toString());
                response = readJsonResponse(exchange, MAX_SYNC_PACKAGE_BYTES);
            } finally {
                exchange.disconnect();
            }
            JSONObject merged = response.getJSONObject("merged");
            JSONObject applyBody = new JSONObject();
            applyBody.put("package", merged);
            applyBody.put("peer", pendingPeer == null ? JSONObject.NULL : pendingPeer);

            notifyDeviceSync("applying", "正在写入合并结果", "写入后还会检查手机数据库完整性。", null);
            JSONObject applied = localSyncRequest(
                    "/api/device-sync/native-apply/" + URLEncoder.encode(ticket, StandardCharsets.UTF_8.name()),
                    "POST", applyBody.toString());
            notifyDeviceSync("completed", "手机和电脑已同步", "两端备份均已保留，本次临时连接即将关闭。", applied);
            pendingPairing = null; pendingSyncTicket = null; pendingPeer = null;
        } catch (Exception error) {
            notifyDeviceSync("error", "同步未完成", safeErrorMessage(error) + "。同步前备份已经保留。", null);
        }
    }

    private HttpsURLConnection openPinnedSyncConnection(
            PairingData pairing, String path, String method) throws Exception {
        X509TrustManager trustManager = new X509TrustManager() {
            @Override public void checkClientTrusted(X509Certificate[] chain, String authType) { }
            @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            @Override public void checkServerTrusted(X509Certificate[] chain, String authType)
                    throws java.security.cert.CertificateException {
                if (chain == null || chain.length == 0) throw new java.security.cert.CertificateException("电脑没有提供同步证书");
                try {
                    String actual = bytesToHex(MessageDigest.getInstance("SHA-256").digest(chain[0].getEncoded()));
                    if (!pairing.fingerprint.equals(actual)) {
                        throw new java.security.cert.CertificateException("同步证书指纹不一致");
                    }
                } catch (java.security.GeneralSecurityException error) {
                    if (error instanceof java.security.cert.CertificateException) throw (java.security.cert.CertificateException) error;
                    throw new java.security.cert.CertificateException("无法核对同步证书", error);
                }
            }
        };
        SSLContext sslContext = SSLContext.getInstance("TLS");
        sslContext.init(null, new TrustManager[]{trustManager}, new SecureRandom());
        URL url = new URL(pairing.baseUrl + path);
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setSSLSocketFactory(sslContext.getSocketFactory());
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(120000);
        connection.setRequestMethod(method);
        connection.setRequestProperty("Authorization", "Bearer " + pairing.token);
        connection.setRequestProperty("Accept", "application/json");
        if ("POST".equals(method)) connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        return connection;
    }

    private JSONObject localSyncRequest(String path, String method, String body) throws Exception {
        if (backendBaseUrl == null) throw new IOException("手机本地学习服务尚未就绪");
        HttpURLConnection connection = (HttpURLConnection) new URL(backendBaseUrl + path).openConnection();
        connection.setConnectTimeout(6000);
        connection.setReadTimeout(120000);
        connection.setRequestMethod(method);
        connection.setRequestProperty("Accept", "application/json");
        if (body != null) {
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            writeJsonBody(connection, body);
        }
        try {
            return readJsonResponse(connection, MAX_SYNC_PACKAGE_BYTES);
        } finally {
            connection.disconnect();
        }
    }

    private void writeJsonBody(HttpURLConnection connection, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        if (bytes.length > MAX_SYNC_PACKAGE_BYTES) throw new IOException("同步数据包超过 33MB 限制");
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(bytes);
            output.flush();
        }
    }

    private JSONObject readJsonResponse(HttpURLConnection connection, int limit) throws Exception {
        int status = connection.getResponseCode();
        InputStream stream = status >= 200 && status < 300
                ? connection.getInputStream() : connection.getErrorStream();
        String raw = stream == null ? "{}" : new String(readLimited(stream, limit), StandardCharsets.UTF_8);
        JSONObject payload = new JSONObject(raw);
        if (status < 200 || status >= 300) {
            throw new IOException(payload.optString("error", "同步服务返回状态 " + status));
        }
        return payload;
    }

    private String bytesToHex(byte[] value) {
        StringBuilder result = new StringBuilder();
        for (byte item : value) result.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        return result.toString();
    }

    private void notifyDeviceSync(String stage, String title, String message, JSONObject extra) {
        runOnUiThread(() -> {
            if (webView == null) return;
            try {
                JSONObject payload = extra == null ? new JSONObject() : new JSONObject(extra.toString());
                payload.put("stage", stage); payload.put("title", title); payload.put("message", message);
                webView.evaluateJavascript("window.CETDeviceSync?.onProgress(" + payload + ");", null);
            } catch (Exception error) {
                Log.e(TAG, "Device sync callback failed", error);
            }
        });
    }

    private void showLoading() {
        String html = "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f0e7;"
                + "color:#202439;font-family:system-ui,'Microsoft YaHei',sans-serif}main{width:min(82vw,520px);"
                + "border-top:5px solid #303b67;padding:32px 0}.k{color:#c4553e;font-weight:800;letter-spacing:.13em}"
                + "h1{font-family:Georgia,serif;font-size:38px;line-height:1.12;margin:12px 0}p{color:#666575;line-height:1.8}</style>"
                + "<main><div class='k'>CET LEARNING DESK</div><h1>正在准备学习台</h1>"
                + "<p>首次启动需要解压本地题库，通常需要十几秒，请不要关闭应用。</p></main>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private void showError(String message) {
        runOnUiThread(() -> {
            String safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
            String html = "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    + "<style>body{padding:38px 24px;background:#f5f0e7;color:#202439;font-family:system-ui}"
                    + "main{border-top:5px solid #c4553e;padding-top:24px}h1{font-size:30px}p{line-height:1.8}</style>"
                    + "<main><h1>学习台暂时无法启动</h1><p>" + safe + "</p>"
                    + "<p>请彻底关闭应用后重新打开；若仍失败，请把此页面截图发给开发者。</p></main>";
            webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
        });
    }

    private void startBackend() {
        try {
            File resourceRoot = new File(getFilesDir(), "app_resources");
            prepareResources(resourceRoot);
            File dataDir = new File(getFilesDir(), "data");
            if (!dataDir.exists() && !dataDir.mkdirs()) {
                throw new IOException("无法创建本地学习数据目录");
            }
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(getApplicationContext()));
            }
            PyObject module = Python.getInstance().getModule("android_backend");
            String url = module.callAttr(
                    "start", dataDir.getAbsolutePath(), resourceRoot.getAbsolutePath()).toString();
            backendBaseUrl = url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
            runOnUiThread(() -> webView.loadUrl(url));
        } catch (Throwable error) {
            Log.e(TAG, "Backend startup failed", error);
            showError("本地题库初始化失败：" + error.getClass().getSimpleName());
        }
    }

    private void prepareResources(File resourceRoot) throws IOException {
        SharedPreferences preferences = getSharedPreferences("cet_runtime", MODE_PRIVATE);
        String installedVersion = preferences.getString("resource_version", "");
        if (RESOURCE_VERSION.equals(installedVersion) && resourceRoot.isDirectory()) {
            return;
        }
        deleteRecursively(resourceRoot);
        if (!resourceRoot.mkdirs() && !resourceRoot.isDirectory()) {
            throw new IOException("无法创建资源目录");
        }
        copyAssetTree("app_resources", resourceRoot);
        preferences.edit().putString("resource_version", RESOURCE_VERSION).apply();
    }

    private void copyAssetTree(String assetPath, File destination) throws IOException {
        String[] children = getAssets().list(assetPath);
        if (children != null && children.length > 0) {
            if (!destination.exists() && !destination.mkdirs()) {
                throw new IOException("无法创建目录：" + destination.getName());
            }
            for (String child : children) {
                copyAssetTree(assetPath + "/" + child, new File(destination, child));
            }
            return;
        }
        File parent = destination.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("无法创建资源父目录");
        }
        try (InputStream input = getAssets().open(assetPath);
             FileOutputStream output = new FileOutputStream(destination)) {
            byte[] buffer = new byte[1024 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            output.getFD().sync();
        }
    }

    private void deleteRecursively(File file) throws IOException {
        if (!file.exists()) {
            return;
        }
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursively(child);
                }
            }
        }
        if (!file.delete()) {
            throw new IOException("无法更新应用资源：" + file.getName());
        }
    }

    private void handleNativeUpdateAction(WebView source, Uri uri) {
        String page = source.getUrl();
        boolean trustedPage = page != null
                && (page.startsWith("http://127.0.0.1:") || page.startsWith("http://localhost:"));
        String ticket = uri.getQueryParameter("ticket");
        if (!trustedPage || !"update".equals(uri.getHost()) || !"/install".equals(uri.getPath())
                || ticket == null || ticket.length() < 32 || ticket.length() > 128) {
            notifyUpdate("error", 0, "更新请求已拒绝", "更新票据无效，请重新点击“检查安全更新”。");
            return;
        }
        backendExecutor.execute(() -> {
            try {
                if (!validateUpdateTicket(ticket)) {
                    throw new IOException("更新票据已过期或未通过本机验证");
                }
                downloadVerifiedUpdate();
            } catch (Throwable error) {
                Log.e(TAG, "Safe update failed", error);
                long saved = largestPartialUpdateBytes();
                notifyUpdate("error", 0, "已安全停止更新", readableUpdateError(error),
                        saved, 0, UPDATE_MAX_ATTEMPTS, saved > 0,
                        saved > 0 ? "download_paused" : "native_update_failed");
            }
        });
    }

    private long largestPartialUpdateBytes() {
        File directory = new File(getCacheDir(), "updates");
        File[] partials = directory.listFiles((dir, name) -> name.endsWith(".apk.part"));
        long largest = 0L;
        if (partials != null) {
            for (File partial : partials) largest = Math.max(largest, partial.length());
        }
        return largest;
    }

    private boolean validateUpdateTicket(String ticket) throws IOException {
        if (backendBaseUrl == null || backendBaseUrl.isEmpty()) {
            return false;
        }
        URL url = new URL(backendBaseUrl + "/api/app/update/native-ticket/"
                + URLEncoder.encode(ticket, StandardCharsets.UTF_8.name())
                + "?platform=android");
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(4000);
        connection.setReadTimeout(6000);
        connection.setRequestMethod("GET");
        try {
            return connection.getResponseCode() == 200;
        } finally {
            connection.disconnect();
        }
    }

    private void downloadVerifiedUpdate() throws Exception {
        notifyUpdate("checking_manifest", 52, "正在读取发布清单", "正在连接固定 GitHub 发布清单。");
        JSONObject manifest = readUpdateManifest();

        int versionCode = manifest.getInt("version_code");
        String version = manifest.getString("version");
        String apkUrl = manifest.getString("apk_url");
        String expectedHash = manifest.getString("sha256").toLowerCase(Locale.ROOT);
        long expectedSize = manifest.optLong("size", 0L);
        if (versionCode <= BuildConfig.VERSION_CODE) {
            throw new IOException("发布版本没有高于当前安装版本");
        }
        if (!expectedHash.matches("[0-9a-f]{64}")) {
            throw new IOException("APK 校验值格式不正确");
        }
        if (expectedSize <= 0 || expectedSize > MAX_APK_BYTES) {
            throw new IOException("APK 体积超出安全限制");
        }

        File updateDir = new File(getCacheDir(), "updates");
        if (!updateDir.exists() && !updateDir.mkdirs()) {
            throw new IOException("无法创建更新缓存目录");
        }
        if (updateDir.getUsableSpace() < Math.max(expectedSize * 2, 40L * 1024L * 1024L)) {
            throw new IOException("设备存储空间不足");
        }
        String hashPrefix = expectedHash.substring(0, 12);
        File apk = new File(updateDir, "cet-learning-desk-" + versionCode + ".apk");
        File partial = new File(updateDir, "cet-learning-desk-" + versionCode + "-" + hashPrefix + ".apk.part");
        downloadApkWithResume(apkUrl, expectedSize, partial, apk);

        notifyUpdate("verifying", 92, "正在核对安装包", "哈希、应用包名、版本号和签名证书必须全部一致。");
        if (!expectedHash.equals(sha256(apk))) {
            apk.delete();
            throw new IOException("APK SHA-256 校验失败");
        }
        try {
            verifyApkIdentity(apk, versionCode);
        } catch (Exception error) {
            apk.delete();
            throw error;
        }
        pendingUpdateApk = apk;
        runOnUiThread(this::requestInstallVerifiedApk);
    }

    private JSONObject readUpdateManifest() throws Exception {
        Exception lastError = null;
        for (int attempt = 1; attempt <= UPDATE_MAX_ATTEMPTS; attempt++) {
            HttpURLConnection connection = null;
            try {
                connection = openTrustedConnection(
                        UPDATE_MANIFEST_URL, true, MANIFEST_READ_TIMEOUT_MS, null);
                try (InputStream input = connection.getInputStream()) {
                    return new JSONObject(new String(
                            readLimited(input, 256 * 1024), StandardCharsets.UTF_8));
                }
            } catch (Exception error) {
                lastError = error;
                if (!isRetryableUpdateError(error) || attempt >= UPDATE_MAX_ATTEMPTS) break;
                notifyUpdate("manifest_retry", 52, "发布清单连接不稳定",
                        "正在第 " + (attempt + 1) + " 次重试发布清单。",
                        0, 0, attempt, false, "manifest_retry");
                sleepBeforeRetry(attempt, error);
            } finally {
                if (connection != null) connection.disconnect();
            }
        }
        if (lastError instanceof SocketTimeoutException) {
            throw new IOException("读取 GitHub 发布清单多次超时，请检查网络后重试", lastError);
        }
        throw new IOException("暂时无法读取 GitHub 发布清单，请稍后重试", lastError);
    }

    private void downloadApkWithResume(
            String apkUrl, long expectedSize, File partial, File destination) throws Exception {
        Exception lastError = null;
        for (int attempt = 1; attempt <= UPDATE_MAX_ATTEMPTS; attempt++) {
            long existing = partial.isFile() ? partial.length() : 0L;
            if (existing < 0 || existing > MAX_APK_BYTES
                    || (expectedSize > 0 && existing > expectedSize)) {
                partial.delete();
                existing = 0L;
            }
            HttpURLConnection connection = null;
            try {
                String range = existing > 0 ? "bytes=" + existing + "-" : null;
                connection = openTrustedConnection(apkUrl, true, APK_READ_TIMEOUT_MS, range);
                int status = connection.getResponseCode();
                if (existing > 0 && status == HttpURLConnection.HTTP_OK) {
                    connection.disconnect();
                    connection = null;
                    if (!partial.delete()) throw new IOException("无法重置不支持续传的临时文件");
                    existing = 0L;
                    connection = openTrustedConnection(apkUrl, true, APK_READ_TIMEOUT_MS, null);
                    status = connection.getResponseCode();
                }
                if (existing > 0) {
                    if (status != HttpURLConnection.HTTP_PARTIAL) {
                        throw new IOException("GitHub 未返回可验证的断点续传响应");
                    }
                    String contentRange = String.valueOf(connection.getHeaderField("Content-Range"));
                    if (!contentRange.startsWith("bytes " + existing + "-")) {
                        throw new IOException("APK 断点位置与 GitHub 响应不一致");
                    }
                }

                long responseLength = connection.getContentLengthLong();
                long total = expectedSize > 0
                        ? expectedSize
                        : (responseLength > 0 ? existing + responseLength : 0L);
                if (total > MAX_APK_BYTES
                        || (expectedSize > 0 && responseLength > 0
                        && responseLength != expectedSize - existing)) {
                    throw new IOException("APK 下载体积与发布清单不一致");
                }

                long downloaded = existing;
                int lastPercent = -1;
                notifyUpdate("downloading", progressPercent(downloaded, total),
                        existing > 0 ? "正在继续下载安全更新" : "正在下载安全更新",
                        downloadProgressCopy(downloaded, total, attempt - 1),
                        downloaded, total, attempt - 1, existing > 0, "");
                try (InputStream input = connection.getInputStream();
                     FileOutputStream output = new FileOutputStream(partial, existing > 0)) {
                    byte[] buffer = new byte[128 * 1024];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        downloaded += count;
                        if (downloaded > MAX_APK_BYTES || (expectedSize > 0 && downloaded > expectedSize)) {
                            throw new IOException("APK 下载超过安全体积限制");
                        }
                        output.write(buffer, 0, count);
                        int percent = progressPercent(downloaded, total);
                        if (percent >= lastPercent + 2) {
                            lastPercent = percent;
                            notifyUpdate("downloading", percent, "正在下载安全更新",
                                    downloadProgressCopy(downloaded, total, attempt - 1),
                                    downloaded, total, attempt - 1, downloaded > 0, "");
                        }
                    }
                    output.getFD().sync();
                }
                if (expectedSize > 0 && downloaded != expectedSize) {
                    throw new IOException("APK 下载不完整");
                }
                if (destination.exists() && !destination.delete()) {
                    throw new IOException("无法替换旧的更新缓存");
                }
                if (!partial.renameTo(destination)) {
                    throw new IOException("无法提交已下载的安装包");
                }
                return;
            } catch (Exception error) {
                lastError = error;
                boolean retryable = isRetryableUpdateError(error);
                if (!retryable) partial.delete();
                if (!retryable || attempt >= UPDATE_MAX_ATTEMPTS) break;
                long saved = partial.isFile() ? partial.length() : 0L;
                notifyUpdate("download_retry", progressPercent(saved, expectedSize),
                        "下载中断，已保留进度",
                        "已保存 " + formatMegabytes(saved) + "，正在第 " + (attempt + 1) + " 次重试。",
                        saved, expectedSize, attempt, saved > 0, "download_retry");
                sleepBeforeRetry(attempt, error);
            } finally {
                if (connection != null) connection.disconnect();
            }
        }
        long saved = partial.isFile() ? partial.length() : 0L;
        String suffix = saved > 0 ? "，已保留 " + formatMegabytes(saved) + "，下次可继续" : "";
        if (lastError instanceof SocketTimeoutException || lastError instanceof ConnectException
                || lastError instanceof UnknownHostException) {
            throw new IOException("APK 下载连接多次超时" + suffix, lastError);
        }
        throw new IOException("APK 下载失败" + suffix + "：" + safeErrorMessage(lastError), lastError);
    }

    private int progressPercent(long downloaded, long total) {
        return total > 0 ? 55 + (int) Math.min(35, downloaded * 35 / total) : 55;
    }

    private String downloadProgressCopy(long downloaded, long total, int retryCount) {
        String copy = formatMegabytes(downloaded);
        if (total > 0) copy += " / " + formatMegabytes(total);
        if (retryCount > 0) copy += " · 已重试 " + retryCount + " 次";
        return copy + "。完成后还会核对哈希、包名和签名证书。";
    }

    private String formatMegabytes(long bytes) {
        return String.format(Locale.ROOT, "%.1f MB", Math.max(0L, bytes) / 1024d / 1024d);
    }

    private boolean isRetryableUpdateError(Throwable error) {
        if (error instanceof SocketTimeoutException || error instanceof ConnectException
                || error instanceof UnknownHostException) return true;
        if (error instanceof UpdateHttpException) {
            int status = ((UpdateHttpException) error).status;
            return status == 429 || status >= 500;
        }
        return false;
    }

    private void sleepBeforeRetry(int attempt, Throwable error) throws InterruptedException {
        long wait = Math.min(10000L, 1500L * (1L << Math.max(0, attempt - 1)));
        if (error instanceof UpdateHttpException) {
            wait = Math.max(wait, ((UpdateHttpException) error).retryAfterMillis);
        }
        Thread.sleep(Math.min(wait, 30000L));
    }

    private String safeErrorMessage(Throwable error) {
        if (error == null || error.getMessage() == null || error.getMessage().trim().isEmpty()) {
            return "网络连接异常";
        }
        return error.getMessage().trim();
    }

    private static final class UpdateHttpException extends IOException {
        final int status;
        final long retryAfterMillis;

        UpdateHttpException(int status, long retryAfterMillis) {
            super("GitHub 下载返回状态 " + status);
            this.status = status;
            this.retryAfterMillis = retryAfterMillis;
        }
    }

    private HttpURLConnection openTrustedConnection(
            String rawUrl, boolean requireRepositoryPath, int readTimeoutMs, String rangeHeader)
            throws IOException {
        URL url = new URL(rawUrl);
        for (int redirect = 0; redirect <= 5; redirect++) {
            validateTrustedUrl(url, requireRepositoryPath && redirect == 0);
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(UPDATE_CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(readTimeoutMs);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent", "CETLearningDeskAndroid/" + BuildConfig.VERSION_NAME);
            if (rangeHeader != null) connection.setRequestProperty("Range", rangeHeader);
            int status = connection.getResponseCode();
            if (status >= 300 && status < 400) {
                String location = connection.getHeaderField("Location");
                connection.disconnect();
                if (location == null || location.isEmpty()) {
                    throw new IOException("GitHub 重定向缺少目标地址");
                }
                url = new URL(url, location);
                continue;
            }
            if (status < 200 || status >= 300) {
                long retryAfterMillis = 0L;
                String retryAfter = connection.getHeaderField("Retry-After");
                if (retryAfter != null && retryAfter.matches("[0-9]+")) {
                    retryAfterMillis = Math.min(30000L, Long.parseLong(retryAfter) * 1000L);
                }
                connection.disconnect();
                throw new UpdateHttpException(status, retryAfterMillis);
            }
            return connection;
        }
        throw new IOException("GitHub 重定向次数过多");
    }

    private void validateTrustedUrl(URL url, boolean requireRepositoryPath) throws IOException {
        if (!"https".equalsIgnoreCase(url.getProtocol())) {
            throw new IOException("更新地址不是 HTTPS");
        }
        Set<String> hosts = new HashSet<>(Arrays.asList(
                "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"));
        if (!hosts.contains(url.getHost().toLowerCase(Locale.ROOT))) {
            throw new IOException("更新地址不属于可信 GitHub 域名");
        }
        if (requireRepositoryPath && (!"github.com".equalsIgnoreCase(url.getHost())
                || !url.getPath().startsWith("/sixinzheng/cet-learning-desk/releases/"))) {
            throw new IOException("更新地址不属于官方仓库");
        }
    }

    private byte[] readLimited(InputStream input, int limit) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int count;
        int total = 0;
        while ((count = input.read(buffer)) != -1) {
            total += count;
            if (total > limit) {
                throw new IOException("发布清单体积异常");
            }
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    private String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new java.io.FileInputStream(file)) {
            byte[] buffer = new byte[128 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                digest.update(buffer, 0, count);
            }
        }
        StringBuilder result = new StringBuilder();
        for (byte item : digest.digest()) {
            result.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        }
        return result.toString();
    }

    @SuppressWarnings("deprecation")
    private Signature[] packageSignatures(PackageInfo info) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && info.signingInfo != null) {
            return info.signingInfo.getApkContentsSigners();
        }
        return info.signatures;
    }

    @SuppressWarnings("deprecation")
    private void verifyApkIdentity(File apk, int expectedVersionCode) throws Exception {
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageManager manager = getPackageManager();
        PackageInfo archive = manager.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
        PackageInfo installed = manager.getPackageInfo(getPackageName(), flags);
        if (archive == null || !getPackageName().equals(archive.packageName)) {
            throw new IOException("APK 包名与当前应用不一致");
        }
        long archiveCode = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                ? archive.getLongVersionCode() : archive.versionCode;
        if (archiveCode != expectedVersionCode || archiveCode <= BuildConfig.VERSION_CODE) {
            throw new IOException("APK 版本号与发布清单不一致");
        }
        Signature[] archiveSignatures = packageSignatures(archive);
        Signature[] installedSignatures = packageSignatures(installed);
        if (archiveSignatures == null || installedSignatures == null
                || archiveSignatures.length != installedSignatures.length) {
            throw new IOException("APK 签名证书数量不一致");
        }
        for (Signature expected : installedSignatures) {
            boolean found = false;
            for (Signature actual : archiveSignatures) {
                if (expected.equals(actual)) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                throw new IOException("APK 签名证书与当前安装不一致");
            }
        }
    }

    private void requestInstallVerifiedApk() {
        if (pendingUpdateApk == null || !pendingUpdateApk.isFile()) {
            notifyUpdate("error", 0, "安装包已失效", "请重新检查并下载更新。");
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !getPackageManager().canRequestPackageInstalls()) {
            notifyUpdate("permission", 96, "需要一次系统授权", "请允许此应用安装自身更新，返回后将继续安装。");
            Intent settingsIntent = new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName()));
            startActivityForResult(settingsIntent, UPDATE_PERMISSION_REQUEST);
            return;
        }
        Uri contentUri = FileProvider.getUriForFile(
                this, getPackageName() + ".fileprovider", pendingUpdateApk);
        Intent install = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(contentUri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        notifyUpdate("waiting_system", 100, "等待系统确认", "Android 将显示安装确认页；取消后可随时重新尝试。");
        startActivity(install);
    }

    private String readableUpdateError(Throwable error) {
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) {
            return "更新校验未通过，当前程序和学习数据均未修改。";
        }
        if ("timeout".equalsIgnoreCase(message.trim())) {
            message = "网络连接超时，请检查 Wi-Fi 后重试";
        }
        return message.replaceAll("[。；;]+$", "") + "。当前程序和学习数据均未修改。";
    }

    private void notifyUpdate(String stage, int percent, String title, String message) {
        notifyUpdate(stage, percent, title, message, 0, 0, 0, false,
                "error".equals(stage) ? "native_update_failed" : "");
    }

    private void notifyUpdate(
            String stage, int percent, String title, String message,
            long downloadedBytes, long totalBytes, int retryCount,
            boolean resumable, String errorCode) {
        runOnUiThread(() -> {
            if (webView == null) return;
            String payload = "{" +
                    "\"stage\":" + JSONObject.quote(stage) + "," +
                    "\"percent\":" + Math.max(0, Math.min(100, percent)) + "," +
                    "\"title\":" + JSONObject.quote(title) + "," +
                    "\"message\":" + JSONObject.quote(message) + "," +
                    "\"downloaded_bytes\":" + Math.max(0, downloadedBytes) + "," +
                    "\"total_bytes\":" + Math.max(0, totalBytes) + "," +
                    "\"retry_count\":" + Math.max(0, retryCount) + "," +
                    "\"resumable\":" + resumable + "," +
                    "\"error_code\":" + JSONObject.quote(errorCode == null ? "" : errorCode) + "}";
            webView.evaluateJavascript("window.CETUpdateNative?.onProgress(" + payload + ");", null);
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        IntentResult syncScan = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (syncScan != null) {
            String contents = syncScan.getContents();
            if (contents == null || contents.trim().isEmpty()) {
                notifyDeviceSync("cancelled", "已取消扫码", "你也可以粘贴电脑显示的完整配对码。", null);
            } else {
                runOnUiThread(() -> webView.evaluateJavascript(
                        "window.CETDeviceSync?.onPairingCode(" + JSONObject.quote(contents) + ");", null));
            }
            return;
        }
        if (requestCode == UPDATE_PERMISSION_REQUEST) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O
                    || getPackageManager().canRequestPackageInstalls()) {
                requestInstallVerifiedApk();
            } else {
                notifyUpdate("cancelled", 0, "尚未获得安装授权", "更新已取消；当前版本和学习数据不受影响。");
            }
            return;
        }
        if (requestCode == FILE_CHOOSER_REQUEST && fileCallback != null) {
            Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == AUDIO_PERMISSION_REQUEST && pendingAudioPermission != null) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                pendingAudioPermission.grant(
                        new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingAudioPermission.deny();
            }
            pendingAudioPermission = null;
            return;
        }
        if (requestCode == SYNC_CAMERA_PERMISSION_REQUEST && pendingSyncScan) {
            pendingSyncScan = false;
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                launchSyncScanner();
            } else {
                notifyDeviceSync("error", "没有相机权限", "请粘贴电脑显示的完整配对码。", null);
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView == null) {
            super.onBackPressed();
            return;
        }
        webView.evaluateJavascript(
                "window.CETHandleNativeBack&&window.CETHandleNativeBack()?'handled':'unhandled'",
                value -> {
                    if ("\"handled\"".equals(value)) return;
                    performDefaultBack();
                });
    }

    private void performDefaultBack() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        if (nativeSpeech != null) {
            nativeSpeech.stop();
            nativeSpeech.shutdown();
            nativeSpeech = null;
        }
        backendExecutor.shutdownNow();
        super.onDestroy();
    }
}
