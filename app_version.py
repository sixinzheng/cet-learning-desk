"""应用版本与官方发布通道的唯一 Python 来源。"""

APP_VERSION = "0.3.0"
ANDROID_VERSION_CODE = 3

GITHUB_OWNER = "sixinzheng"
GITHUB_REPOSITORY = "cet-learning-desk"
GITHUB_REPOSITORY_URL = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}"
)
GITHUB_RELEASES_URL = f"{GITHUB_REPOSITORY_URL}/releases"
GITHUB_LATEST_RELEASE_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/latest"
)

# 原生端只从这两个固定地址获取可执行更新，不接受网页或用户传入的下载地址。
WINDOWS_UPDATER_MANIFEST_URL = (
    f"{GITHUB_REPOSITORY_URL}/releases/latest/download/latest.json"
)
ANDROID_UPDATER_MANIFEST_URL = (
    f"{GITHUB_REPOSITORY_URL}/releases/latest/download/android-latest.json"
)
