import threading
import webbrowser

from flask import Flask, redirect, render_template, url_for

from database import init_db
from config import get_api_key, get_session_secret, load_config
from runtime_paths import resource_path
from app_version import APP_VERSION
from services.update_service import current_platform


def create_app():
    app = Flask(
        __name__,
        template_folder=resource_path('templates'),
        static_folder=resource_path('static'),
    )
    app.config['JSON_AS_ASCII'] = False
    app.json.sort_keys = False
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.secret_key = get_session_secret()
    app.jinja_env.auto_reload = True
    cfg = load_config()
    app.config['DEEPSEEK_KEY'] = bool(get_api_key())
    app.config['DEEPSEEK_URL'] = cfg['deepseek_base_url']

    # 静态资源自动缓存破除：按文件修改时间出版本号，改动文件后刷新页面即拿到新版
    def _static_version(filename):
        import os
        try:
            return int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        except OSError:
            return 0

    app.jinja_env.globals['asset'] = lambda filename: '/static/{}?v={}'.format(filename, _static_version(filename))

    init_db()

    # 新算法首次启用时只写入一次“算法重新校准”快照；之后页面读取仍实时计算。
    from database import get_db
    migration_db = get_db()
    latest = migration_db.execute(
        "SELECT algorithm_version FROM user_level ORDER BY id DESC LIMIT 1"
    ).fetchone()
    migration_db.close()
    if not latest or latest['algorithm_version'] != '2.0':
        from services.level_service import calculate_level
        calculate_level(reason='algorithm_upgrade')

    # 依赖缺失必须在启动时明确失败，不能静默丢失整组功能。
    from routes.api_cloze import bp as cloze_bp
    from routes.api_export import bp as export_bp
    from routes.api_level import bp as level_bp
    from routes.api_notes import bp as notes_bp
    from routes.api_practice import bp as practice_bp
    from routes.api_reading import bp as reading_bp
    from routes.api_study import bp as study_bp
    from routes.api_words import bp as words_bp
    from routes.api_writing import bp as writing_bp
    from routes.api_ai import bp as ai_bp
    from routes.api_update import bp as update_bp

    app.register_blueprint(words_bp, url_prefix='/api/words')
    app.register_blueprint(study_bp, url_prefix='/api/study')
    app.register_blueprint(level_bp, url_prefix='/api/level')
    app.register_blueprint(reading_bp, url_prefix='/api/reading')
    app.register_blueprint(writing_bp, url_prefix='/api/writing')
    app.register_blueprint(notes_bp, url_prefix='/api/notes')
    app.register_blueprint(export_bp, url_prefix='/api/export')
    app.register_blueprint(practice_bp, url_prefix='/api/practice')
    app.register_blueprint(cloze_bp, url_prefix='/api/practice')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(update_bp, url_prefix='/api/app/update')

    # 只有用户在阅读页明确开启过自动补库时才跨重启恢复；
    # 测试库和新安装默认不会发起付费 AI 请求。
    from services.reading_inventory_service import resume_refill_worker_if_enabled
    resume_refill_worker_if_enabled()

    @app.route('/')
    def index():
        return render_template('index.html')

    page_templates = {
        'learn': 'learn.html',
        'growth': 'growth.html',
        'profile': 'profile.html',
        'study': 'study.html',
        'review': 'review.html',
        'reading': 'reading.html',
        'listening': 'listening.html',
        'writing': 'writing.html',
        'cloze': 'cloze.html',
        'control': 'control.html',
        'notes': 'notes.html',
        'export': 'export.html',
        'diagnostic': 'diagnostic.html',
    }

    @app.route('/<any(learn,growth,profile,study,review,reading,listening,writing,cloze,control,notes,export,diagnostic):page>')
    def page(page):
        if page == 'profile':
            return render_template(
                page_templates[page],
                ai_configured=bool(get_api_key()),
                app_version=APP_VERSION,
                app_platform=current_platform(),
            )
        return render_template(page_templates[page])

    @app.route('/level')
    def legacy_level():
        return redirect(url_for('page', page='growth') + '#rank')

    @app.route('/summary')
    def legacy_summary():
        return redirect(url_for('page', page='growth') + '#summary')

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    return app


if __name__ == '__main__':
    app = create_app()
    cfg = load_config()
    port = cfg.get('port', 5099)

    def open_browser():
        webbrowser.open(f'http://localhost:{port}')

    threading.Timer(1.0, open_browser).start()
    print(f"\n[四六级单词助手] 已启动 -> http://localhost:{port}\n")
    app.run(host='127.0.0.1', port=port, debug=True)
