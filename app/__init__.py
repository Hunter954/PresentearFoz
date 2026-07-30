from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import csrf, db, login_manager, migrate


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .main.routes import bp as main_bp
    from .shop.routes import bp as shop_bp
    from .auth.routes import bp as auth_bp
    from .admin.routes import bp as admin_bp
    from .api.routes import bp as api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    from .cli import register_commands
    register_commands(app)

    from .utils import inject_global_context
    app.context_processor(inject_global_context)

    from datetime import datetime, timezone
    from decimal import Decimal
    from zoneinfo import ZoneInfo

    @app.template_filter("brl")
    def brl(value):
        if value is None:
            return ""
        text = f"R$ {Decimal(value):,.2f}"
        return text.replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("datetime_br")
    def datetime_br(value):
        if not value:
            return "—"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")

    @app.context_processor
    def inject_now():
        return {"now": lambda: datetime.now(ZoneInfo("America/Sao_Paulo"))}


    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'self' data:; "
            "frame-ancestors 'self'; base-uri 'self'; form-action 'self' https://wa.me",
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": "Sessão expirada. Atualize a página e tente novamente."}), 400
        return render_template("errors/400.html", message="Sessão expirada. Atualize a página e tente novamente."), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app
