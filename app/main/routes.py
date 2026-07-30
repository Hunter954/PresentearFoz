from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, render_template, request, send_from_directory, url_for
from sqlalchemy import text

from ..extensions import db
from ..models import AnalyticsEvent, Banner, Category, ClientLogo, Product
from ..utils import setting, visitor_token

bp = Blueprint("main", __name__)


def track(event_type: str, **kwargs):
    if request.path.startswith("/admin") or request.path.startswith("/static"):
        return
    db.session.add(
        AnalyticsEvent(
            event_type=event_type,
            path=request.path,
            visitor_token=visitor_token(),
            metadata_json=kwargs or {},
        )
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


@bp.get("/")
def home():
    banners = Banner.query.filter_by(is_active=True).order_by(Banner.sort_order, Banner.id).all()
    categories = (
        Category.query.filter_by(is_active=True, is_featured=True)
        .order_by(Category.sort_order, Category.name)
        .limit(8)
        .all()
    )
    featured_products = (
        Product.query.filter_by(status="active", is_featured=True)
        .order_by(Product.updated_at.desc())
        .limit(12)
        .all()
    )
    new_products = (
        Product.query.filter_by(status="active", is_new=True)
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )
    clients = (
        ClientLogo.query.filter_by(is_active=True)
        .order_by(ClientLogo.sort_order, ClientLogo.name)
        .all()
    )
    track("page_view", page="home")
    return render_template(
        "home.html",
        banners=banners,
        categories=categories,
        featured_products=featured_products,
        new_products=new_products,
        clients=clients,
    )


@bp.get("/sobre")
def about():
    track("page_view", page="about")
    return render_template("about.html")


@bp.get("/contato")
def contact():
    track("page_view", page="contact")
    return render_template("contact.html")


@bp.get("/politica-de-privacidade")
def privacy():
    return render_template("privacy.html")


@bp.get("/health")
def health():
    # Liveness: o Railway precisa apenas confirmar que o processo HTTP subiu.
    # A disponibilidade do banco é validada separadamente em /ready.
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@bp.get("/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
        db.session.rollback()
        return {"status": "ok", "database": "ok", "time": datetime.now(timezone.utc).isoformat()}
    except Exception:
        db.session.rollback()
        return {"status": "error", "database": "unavailable", "time": datetime.now(timezone.utc).isoformat()}, 503


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename):
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    return send_from_directory(upload_root, filename, max_age=31536000)


@bp.get("/robots.txt")
def robots():
    content = f"User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: {current_app.config['SITE_URL']}/sitemap.xml\n"
    return Response(content, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    urls = [
        (url_for("main.home", _external=True), None),
        (url_for("shop.catalog", _external=True), None),
        (url_for("main.about", _external=True), None),
        (url_for("main.contact", _external=True), None),
    ]
    for category in Category.query.filter_by(is_active=True).all():
        urls.append((url_for("shop.catalog", categoria=category.slug, _external=True), category.updated_at))
    for product in Product.query.filter_by(status="active").all():
        urls.append((url_for("shop.product_detail", slug=product.slug, _external=True), product.updated_at))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for location, modified in urls:
        xml.append("<url>")
        xml.append(f"<loc>{location}</loc>")
        if modified:
            xml.append(f"<lastmod>{modified.date().isoformat()}</lastmod>")
        xml.append("</url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")
