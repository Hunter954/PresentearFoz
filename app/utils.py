from __future__ import annotations

import re
import secrets
import unicodedata
from pathlib import Path
from uuid import uuid4

from flask import current_app, request, session, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

from .extensions import db
from .models import AuditLog, MediaAsset, SiteSetting

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or secrets.token_hex(4)


def unique_slug(model, value: str, current_id: int | None = None) -> str:
    base = slugify(value)
    candidate = base
    counter = 2
    while True:
        query = model.query.filter_by(slug=candidate)
        if current_id:
            query = query.filter(model.id != current_id)
        if query.first() is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


def setting(key: str, default=None):
    row = SiteSetting.query.filter_by(key=key).first()
    if not row or row.value in (None, ""):
        return default
    if row.value_type == "bool":
        return str(row.value).lower() in {"1", "true", "yes", "on", "sim"}
    if row.value_type == "int":
        try:
            return int(row.value)
        except (TypeError, ValueError):
            return default
    return row.value


def set_setting(key: str, value, **kwargs):
    row = SiteSetting.query.filter_by(key=key).first()
    if not row:
        row = SiteSetting(key=key)
        db.session.add(row)
    row.value = "" if value is None else str(value)
    for field in ("value_type", "group_name", "label", "sort_order"):
        if field in kwargs:
            setattr(row, field, kwargs[field])
    return row


def upload_image(file_storage, folder: str = "general") -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Formato inválido. Use PNG, JPG, JPEG, WEBP ou GIF.")

    unique_name = f"{uuid4().hex}.{extension}"
    relative_dir = Path(folder)
    absolute_dir = Path(current_app.config["UPLOAD_FOLDER"]) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)
    absolute_path = absolute_dir / unique_name

    try:
        image = Image.open(file_storage.stream)
        image.verify()
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        if extension == "gif":
            file_storage.stream.seek(0)
            file_storage.save(absolute_path)
        else:
            image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
            if extension in {"jpg", "jpeg"}:
                if image.mode not in {"RGB", "L"}:
                    background = Image.new("RGB", image.size, "white")
                    if "A" in image.getbands():
                        background.paste(image, mask=image.getchannel("A"))
                    else:
                        background.paste(image)
                    image = background
                image.save(absolute_path, format="JPEG", quality=88, optimize=True, progressive=True)
            elif extension == "webp":
                image.save(absolute_path, format="WEBP", quality=88, method=6)
            else:
                image.save(absolute_path, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("O arquivo enviado não é uma imagem válida.") from exc

    relative_path = f"uploads/{relative_dir.as_posix()}/{unique_name}"
    asset = MediaAsset(
        original_name=filename,
        file_name=unique_name,
        file_path=relative_path,
        mime_type=file_storage.mimetype,
        size_bytes=absolute_path.stat().st_size,
        uploaded_by_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(asset)
    return relative_path


def media_url(path: str | None) -> str:
    if not path:
        return url_for("static", filename="img/product-placeholder.svg")
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("uploads/"):
        return url_for("main.uploaded_file", filename=path.removeprefix("uploads/"))
    return url_for("static", filename=path)


def audit(action: str, entity_type=None, entity_id=None, details=None):
    db.session.add(
        AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=details or {},
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        )
    )


def visitor_token() -> str:
    token = session.get("visitor_token")
    if not token:
        token = secrets.token_urlsafe(18)
        session["visitor_token"] = token
        session.permanent = True
    return token


def inject_global_context():
    from .services.cart_service import get_current_cart
    from .models import Category

    cart = get_current_cart(create=False)
    nav_categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).limit(8).all()
    settings = {
        "company_name": setting("company_name", "Presentear Foz"),
        "whatsapp": setting("whatsapp", "5545998119520"),
        "whatsapp_display": setting("whatsapp_display", "(45) 99811-9520"),
        "instagram": setting("instagram", "presentearfoz"),
        "email": setting("email", ""),
        "address": setting("address", "Foz do Iguaçu - PR"),
        "primary_color": setting("primary_color", "#5F3B73"),
        "accent_color": setting("accent_color", "#FFC82E"),
        "site_url": current_app.config["SITE_URL"],
    }
    return {
        "site_settings": settings,
        "current_cart": cart,
        "cart_count": cart.item_count if cart else 0,
        "media_url": media_url,
        "setting": setting,
        "nav_categories": nav_categories,
    }
