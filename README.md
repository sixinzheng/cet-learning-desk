# 四六级学习台

一套本地优先的 CET-4/CET-6 英语学习网站，连接每日背词、艾宾浩斯复习、阅读与听力训练、作文批改、学习笔记、AI 学习助理和科举十级段位。

项目同时支持：

- 浏览器本地运行：Flask + SQLite + Jinja + 原生 JavaScript；
- Windows 桌面安装版：Tauri + PyInstaller sidecar；
- Android 安装版：WebView + Chaquopy 内嵌 Python。

## 产品特点

- 五态单词学习与复习调度；
- 六维段位 V3：词汇、阅读、听力、写作、记忆保持和有效投入；
- 四六级阅读文章库、六档难度和补库任务；
- DeepSeek 流式学习助理、作文批改和图片文字识别；
- 本地笔记、成长账单、热力图和可解释段位贡献；
- 桌面、平板和手机响应式布局。

AI 是可选能力。未配置 API Key 时，背词、复习、本地题库、笔记和大部分成长统计仍可使用。

## 本地启动

建议使用 Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py
```

终端会显示实际访问地址。首次启动会从 `resources/distribution/vocab.seed.db` 创建一份本地学习数据库。

用户数据、AI 配置和学习记录保存在本机运行目录，不属于源码仓库，也不会被 Git 跟踪。

## 测试

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

JavaScript 语法可用 Node.js 检查：

```powershell
Get-ChildItem static/js -Filter *.js | ForEach-Object { node --check $_.FullName }
```

## Windows 与 Android 构建

Windows 构建说明见 [desktop/README.md](desktop/README.md)。

Android 构建说明见 [android/README.md](android/README.md)。生成的安装包、签名密钥、Gradle 缓存和用户数据库均被 `.gitignore` 排除。

## 隐私与安全

- 不要把 `data/`、完整 API Key、Android 发布密钥或本机日志提交到仓库；
- Windows API Key 使用当前用户凭据管理器保存；Android 使用 Keystore；
- 作文图片仅在一次 OCR 请求中使用，应用逻辑不会把原图写入本地数据库；
- AI 写入笔记或记忆前需要用户确认；
- 段位分数是本站学习证据的能力参考，不直接预测真实 CET 成绩。

## 数据与第三方材料

发行种子词库包含由 [ECDICT](https://github.com/skywind3000/ECDICT) 数据整理的词条。ECDICT 使用 MIT License，具体声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

阅读材料为基于公开事实来源重新编写的本站训练内容，不宣称是媒体原文或真实四六级真题。

## 许可证

当前仓库暂未授予项目源码的开源许可证。公开可见不等于允许复制、修改或商用；第三方材料继续遵循各自许可证。

