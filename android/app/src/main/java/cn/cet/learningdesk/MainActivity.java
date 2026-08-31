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
import android.util.Log;
import android.view.View;
import android.webkit.CookieManager;
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

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String TAG = "CETLearningDesk";
    private static final String RESOURCE_VERSION = BuildConfig.VERSION_NAME;
    private static final String UPDATE_MANIFEST_URL = "https://github.com/sixinzheng/cet-learning-desk/releases/latest/download/android-latest.json";
    private static final long MAX_APK_BYTES = 250L * 1024L * 1024L;
    private static final int UPDATE_PERMISSION_REQUEST = 4103;
    private static final int FILE_CHOOSER_REQUEST = 4101;
    private static final int AUDIO_PERMISSION_REQUEST = 4102;

    private final ExecutorService backendExecutor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingAudioPermission;
    private String backendBaseUrl;
    private File pendingUpdateApk;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(48, 59, 103));
        getWindow().setNavigationBarColor(Color.rgb(245, 240, 231));
        SecureStore.init(this);
        configureWebView();
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
                notifyUpdate("error", 0, "已安全停止更新", readableUpdateError(error));
            }
        });
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
        notifyUpdate("checking_native", 52, "正在验证更新", "Android 正在读取固定 GitHub 发布清单。");
        HttpURLConnection manifestConnection = openTrustedConnection(UPDATE_MANIFEST_URL, true);
        JSONObject manifest;
        try (InputStream input = manifestConnection.getInputStream()) {
            manifest = new JSONObject(new String(readLimited(input, 256 * 1024), StandardCharsets.UTF_8));
        } finally {
            manifestConnection.disconnect();
        }

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
        if (expectedSize < 0 || expectedSize > MAX_APK_BYTES) {
            throw new IOException("APK 体积超出安全限制");
        }

        File updateDir = new File(getCacheDir(), "updates");
        if (!updateDir.exists() && !updateDir.mkdirs()) {
            throw new IOException("无法创建更新缓存目录");
        }
        if (updateDir.getUsableSpace() < Math.max(expectedSize * 2, 40L * 1024L * 1024L)) {
            throw new IOException("设备存储空间不足");
        }
        File apk = new File(updateDir, "cet-learning-desk-" + versionCode + ".apk");
        HttpURLConnection apkConnection = openTrustedConnection(apkUrl, true);
        long contentLength = apkConnection.getContentLengthLong();
        if (contentLength > MAX_APK_BYTES || (expectedSize > 0 && contentLength > 0 && expectedSize != contentLength)) {
            apkConnection.disconnect();
            throw new IOException("APK 下载体积与发布清单不一致");
        }

        long downloaded = 0;
        int lastPercent = -1;
        try (InputStream input = apkConnection.getInputStream();
             FileOutputStream output = new FileOutputStream(apk, false)) {
            byte[] buffer = new byte[128 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                downloaded += count;
                if (downloaded > MAX_APK_BYTES) {
                    throw new IOException("APK 下载超过安全体积限制");
                }
                output.write(buffer, 0, count);
                long total = expectedSize > 0 ? expectedSize : contentLength;
                int percent = total > 0 ? 55 + (int) Math.min(35, downloaded * 35 / total) : 65;
                if (percent >= lastPercent + 2) {
                    lastPercent = percent;
                    notifyUpdate("downloading", percent, "正在下载安全更新", "下载完成后还会核对哈希、包名和签名证书。");
                }
            }
            output.getFD().sync();
        } catch (Throwable error) {
            apk.delete();
            throw error;
        } finally {
            apkConnection.disconnect();
        }
        if (expectedSize > 0 && downloaded != expectedSize) {
            apk.delete();
            throw new IOException("APK 下载不完整");
        }

        notifyUpdate("verifying", 92, "正在核对安装包", "哈希、应用包名、版本号和签名证书必须全部一致。");
        if (!expectedHash.equals(sha256(apk))) {
            apk.delete();
            throw new IOException("APK SHA-256 校验失败");
        }
        verifyApkIdentity(apk, versionCode);
        pendingUpdateApk = apk;
        runOnUiThread(this::requestInstallVerifiedApk);
    }

    private HttpURLConnection openTrustedConnection(String rawUrl, boolean requireRepositoryPath)
            throws IOException {
        URL url = new URL(rawUrl);
        for (int redirect = 0; redirect <= 5; redirect++) {
            validateTrustedUrl(url, requireRepositoryPath && redirect == 0);
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(20000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent", "CETLearningDeskAndroid/" + BuildConfig.VERSION_NAME);
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
                connection.disconnect();
                throw new IOException("GitHub 下载返回状态 " + status);
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
        return message + "。当前程序和学习数据均未修改。";
    }

    private void notifyUpdate(String stage, int percent, String title, String message) {
        runOnUiThread(() -> {
            if (webView == null) return;
            String payload = "{" +
                    "\"stage\":" + JSONObject.quote(stage) + "," +
                    "\"percent\":" + Math.max(0, Math.min(100, percent)) + "," +
                    "\"title\":" + JSONObject.quote(title) + "," +
                    "\"message\":" + JSONObject.quote(message) + "}";
            webView.evaluateJavascript("window.CETUpdateNative?.onProgress(" + payload + ");", null);
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
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
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        backendExecutor.shutdownNow();
        super.onDestroy();
    }
}
