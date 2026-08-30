# Windows 桌面安装版

桌面版采用 Tauri 外壳 + PyInstaller Flask sidecar。程序资源随安装包只读分发，用户数据写入：

`%LOCALAPPDATA%\CETLearningDesk\data`

首次启动会从 `resources/distribution/vocab.seed.db` 复制一份干净数据库。更新或卸载程序不会主动覆盖学习数据。

首次建库采用直接写入、安装标记和 SQLite 完整性检查，不依赖临时文件改名；因此也兼容 Windows 加密目录或被系统识别为不同卷的本地数据位置。若本地服务仍无法启动，界面会显示可重试提示，详细错误仅记录在：

`%LOCALAPPDATA%\CETLearningDesk\logs\backend-error.log`

## 构建

要求：Windows 10/11 x64、Node.js、Rust MSVC 工具链、WebView2。

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop\build_windows.ps1
```

构建脚本会：

1. 生成不含个人记录的发行种子库；
2. 打包 Flask sidecar；
3. 构建当前用户安装模式的 NSIS 安装程序。

安装包位于 `desktop\src-tauri\target\release\bundle\nsis`。

## 发布前检查

- 不得直接把 `data/vocab.db` 放入安装包。
- 用空白 Windows 用户安装并完成一次首启、学习、退出和再次启动。
- 升级安装后确认 `%LOCALAPPDATA%\CETLearningDesk\data\vocab.db` 未被覆盖。
- 正式公开分发前对安装程序和主程序进行代码签名。
