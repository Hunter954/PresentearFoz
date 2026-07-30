from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from ..utils import audit

bp = Blueprint("auth", __name__, url_prefix="/admin")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.is_active or not user.check_password(password):
            flash("E-mail ou senha inválidos.", "danger")
            return render_template("auth/login.html", email=email), 401
        login_user(user, remember=True)
        user.last_login_at = datetime.now(timezone.utc)
        audit("login", "user", user.id)
        db.session.commit()
        next_url = request.args.get("next")
        if next_url:
            base = urlparse(request.host_url)
            target = urlparse(urljoin(request.host_url, next_url))
            if (target.scheme, target.netloc) != (base.scheme, base.netloc):
                next_url = None
        return redirect(next_url or url_for("admin.dashboard"))

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    audit("logout", "user", current_user.id)
    db.session.commit()
    logout_user()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("auth.login"))
