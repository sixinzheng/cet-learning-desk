package cn.cet.learningdesk;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
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

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String TAG = "CETLearningDesk";
    private static final String RESOURCE_VERSION = "0.2.0";
    private static final int FILE_CHOOSER_REQUEST = 4101;
    private static final int AUDIO_PERMISSION_REQUEST = 4102;

    private final ExecutorService backendExecutor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingAudioPermission;

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
        settings.setUserAgentString(settings.getUserAgentString() + " CETLearningDeskAndroid/0.2.0");
        CookieManager.getInstance().setAcceptCookie(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
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

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
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
