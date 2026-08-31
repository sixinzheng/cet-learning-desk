# 稳定发布与安全更新

应用内更新只读取公开仓库 `sixinzheng/cet-learning-desk` 的稳定 GitHub Release。源码浏览器模式不会执行 `git pull`，也不会修改当前工作区。

## 首次启用

`v0.3.0` 是首个公开发布且携带更新器的版本，但其 Android APK 遗漏了运行时 `seed` 资源导入路径，真机启动会报 `ModuleNotFoundError: No module named 'seed'`，因此 Android `v0.3.0` 不能作为可用引导版，也无法从应用内自助升级。

`v0.3.1` 是首个经过真机启动、同签名覆盖安装、SQLite 数据保留和 Android Keystore 配置保留验证的 Android 引导版。发布后：

- Windows 0.1.0、Android 0.2.0 以及 Android 0.3.0 用户需要手动覆盖安装一次 `v0.3.1`；
- Windows 0.3.0 可以使用现有安全更新入口升级到 `v0.3.1`；
- 从可正常启动的 `v0.3.1` 起，Windows 与 Android 才都具备应用内安全升级能力。

不得静默替换已经发布的 `v0.3.0` 标签或资产。修复必须使用递增版本号和新的稳定 Release，并在更新说明中明确 Android 手动覆盖安装要求。

## GitHub Actions Secrets

发布稳定标签前，在仓库 Actions Secrets 配置：

- `TAURI_SIGNING_PRIVATE_KEY`：Tauri updater 私钥完整内容；私钥不得提交。
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`：当前首发密钥为空密码，因此无需创建该 Secret；以后若在保持公钥兼容的前提下换用带密码密钥再填写。
- `ANDROID_KEYSTORE_BASE64`：现有 Android 发布 JKS 的 Base64 内容。
- `ANDROID_KEYSTORE_PASSWORD`：现有发布密钥密码。
- `ANDROID_KEY_ALIAS`：固定为 `cet-learning-desk`。

标签必须与 `app_version.py` 完全一致，例如 `v0.3.1`。工作流先执行测试与版本校验，再分别构建 Windows 和 Android，最后生成 `latest.json`、`android-latest.json` 与 `SHA256SUMS.txt` 并发布稳定 Release。

每个稳定版本必须提供 `docs/releases/vX.Y.Z.md`。GitHub Release、Windows 更新清单和 Android 更新清单共同读取这份版本化说明；缺失或空文件会在版本契约检查阶段阻止发布。

Windows 构建先生成 NSIS 安装器，再调用 Tauri 独立签名器。这样空密码首发密钥也能在 GitHub Actions 中非交互签名，不会卡在密码提示。

## 数据保护

用户确认安装后，后端先用 SQLite Online Backup API 创建一致性副本，再执行 `PRAGMA quick_check`。只有校验通过才向原生外壳发放短期更新票据，最近仅保留 3 份更新前备份。

Windows 使用 Tauri updater 公钥验证签名；Android 固定读取官方仓库清单，并校验 SHA-256、包名、递增 versionCode 与已安装应用的签名证书，最终仍由 Android 系统安装器要求用户确认。
