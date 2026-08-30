use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};
use tauri_plugin_updater::UpdaterExt;


struct BackendProcess(Mutex<Option<CommandChild>>);
struct ReadyUpdateTicket(Mutex<Option<String>>);


fn notify_frontend(
    app: &tauri::AppHandle,
    stage: &str,
    percent: u64,
    title: &str,
    message: &str,
) {
    let payload = serde_json::json!({
        "stage": stage,
        "percent": percent.min(100),
        "title": title,
        "message": message,
    });
    if let Some(window) = app.get_webview_window("main") {
        let script = format!("window.CETUpdateNative?.onProgress({payload});");
        let _ = window.eval(&script);
    }
}


async fn install_signed_update(app: tauri::AppHandle) {
    notify_frontend(
        &app,
        "checking_native",
        52,
        "正在验证更新",
        "Windows 正在核对 Tauri 签名与稳定发布清单。",
    );
    let result = async {
        let Some(update) = app.updater()?.check().await? else {
            notify_frontend(&app, "current", 100, "已经是最新版本", "未发现可安装的稳定更新。");
            return Ok::<(), tauri_plugin_updater::Error>(());
        };
        let progress_app = app.clone();
        let finish_app = app.clone();
        let mut downloaded: u64 = 0;
        update
            .download_and_install(
                move |chunk_length, content_length| {
                    downloaded = downloaded.saturating_add(chunk_length as u64);
                    let percent = content_length
                        .filter(|total| *total > 0)
                        .map(|total| 55 + downloaded.saturating_mul(35) / total)
                        .unwrap_or(65);
                    notify_frontend(
                        &progress_app,
                        "downloading",
                        percent,
                        "正在下载签名更新",
                        "下载完成后会再次验证签名，再进入被动安装。",
                    );
                },
                move || {
                    notify_frontend(
                        &finish_app,
                        "verifying",
                        92,
                        "正在核对更新签名",
                        "签名不匹配时会立即停止，不会覆盖当前版本。",
                    );
                },
            )
            .await?;
        notify_frontend(
            &app,
            "installing",
            100,
            "更新已验证",
            "即将关闭学习台并完成安装，随后自动重启。",
        );
        app.restart();
    }
    .await;
    if let Err(error) = result {
        notify_frontend(
            &app,
            "error",
            0,
            "已安全停止更新",
            &format!("签名、下载或安装校验失败：{error}"),
        );
    }
}


pub fn run() {
    let safe_update_plugin = tauri::plugin::Builder::<tauri::Wry>::new("safe-update-navigation")
        .on_navigation(|webview, url| {
            if url.scheme() != "cetlearningdesk" {
                return true;
            }
            if url.host_str() != Some("update") || url.path() != "/install" {
                return false;
            }
            let supplied = url
                .query_pairs()
                .find(|(key, _)| key == "ticket")
                .map(|(_, value)| value.into_owned())
                .unwrap_or_default();
            let app = webview.app_handle().clone();
            let valid = {
                let state = app.state::<ReadyUpdateTicket>();
                let mut stored = state.0.lock().unwrap();
                if stored.as_deref() == Some(supplied.as_str()) {
                    stored.take();
                    true
                } else {
                    false
                }
            };
            if valid {
                tauri::async_runtime::spawn(install_signed_update(app));
            } else {
                notify_frontend(
                    &app,
                    "error",
                    0,
                    "更新请求已拒绝",
                    "更新票据无效或已过期，请重新点击“检查安全更新”。",
                );
            }
            false
        })
        .build();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(safe_update_plugin)
        .manage(BackendProcess(Mutex::new(None)))
        .manage(ReadyUpdateTicket(Mutex::new(None)))
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("cet-backend")?
                .args(["--parent-pid", &std::process::id().to_string()]);
            let (mut receiver, child) = sidecar.spawn()?;
            *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut ready = false;
                let mut error_shown = false;
                while let Some(event) = receiver.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            let output = String::from_utf8_lossy(&bytes);
                            for line in output.lines() {
                                let line = line.trim();
                                if let Some(url) = line.strip_prefix("CET_BACKEND_READY=") {
                                    ready = true;
                                    if let Some(window) = handle.get_webview_window("main") {
                                        let script = format!("window.location.replace({:?});", url);
                                        let _ = window.eval(&script);
                                    }
                                } else if let Some(ticket) = line.strip_prefix("CET_UPDATE_TICKET=") {
                                    let state = handle.state::<ReadyUpdateTicket>();
                                    *state.0.lock().unwrap() = Some(ticket.to_string());
                                } else if let Some(message) = line.strip_prefix("CET_BACKEND_ERROR=") {
                                    error_shown = true;
                                    if let Some(window) = handle.get_webview_window("main") {
                                        let script = format!("window.showBackendError({:?});", message);
                                        let _ = window.eval(&script);
                                    }
                                }
                            }
                        }
                        CommandEvent::Error(message) => eprintln!("backend: {message}"),
                        CommandEvent::Terminated(payload) => {
                            eprintln!("backend terminated: {:?}", payload.code);
                            if !ready && !error_shown {
                                if let Some(window) = handle.get_webview_window("main") {
                                    let _ = window.eval(
                                        "window.showBackendError('本地学习服务未能启动，请关闭后重新打开。');",
                                    );
                                }
                            }
                        }
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("无法启动四六级学习台");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            let state = app_handle.state::<BackendProcess>();
            let child = { state.0.lock().unwrap().take() };
            if let Some(child) = child {
                let _ = child.kill();
            }
        }
    });
}
