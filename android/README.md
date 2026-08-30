# Android 安装版

Android 版使用原生 WebView + Chaquopy 内嵌 Python 3.12，在手机本机启动 Flask 与 SQLite。它不是远程网页壳，背词、段位、笔记与本地题库无需连接电脑；DeepSeek 等联网能力仍需要网络和用户自己的 API Key。

## 构建

要求：JDK 17/21、Android SDK 36、Windows PowerShell 和可访问 Maven Central/Chaquopy 仓库的网络。

```powershell
powershell -ExecutionPolicy Bypass -File .\android\build_android.ps1
```

脚本会生成 Android 专用源码/资源快照、校验 Gradle 发行包，并构建 arm64-v8a APK。正式分发前还需要使用项目发布密钥签名，不能把调试密钥或个人密钥提交到项目。

构建成功后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\android\sign_android.ps1
```

首次签名会在 `%LOCALAPPDATA%\CETLearningDesk\signing` 生成唯一发布密钥，密码用 Windows 当前用户 DPAPI 加密保存。发布密钥绝不能和 APK 一起公开分发；若密钥丢失，已安装用户将无法直接升级到后续版本。

用户数据位于 Android 应用私有目录；API Key 使用 Android Keystore AES-GCM 加密。卸载应用会由 Android 一并删除本地学习数据，因此正式版应在卸载前提供导出提醒。
