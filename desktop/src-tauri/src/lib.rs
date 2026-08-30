use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};


struct BackendProcess(Mutex<Option<CommandChild>>);


pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(None)))
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
                                if let Some(url) = line.trim().strip_prefix("CET_BACKEND_READY=") {
                                    ready = true;
                                    if let Some(window) = handle.get_webview_window("main") {
                                        let script = format!(
                                            "window.location.replace({:?});",
                                            url
                                        );
                                        let _ = window.eval(&script);
                                    }
                                } else if let Some(message) = line.trim().strip_prefix("CET_BACKEND_ERROR=") {
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
                                        "window.showBackendError('本地学习服务未能启动，请关闭后重新打开。');"
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
