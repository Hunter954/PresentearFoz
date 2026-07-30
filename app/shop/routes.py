from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from ..extensions import db
from ..models import AnalyticsEvent, Category, Product
from ..services.cart_service import build_whatsapp_message, get_current_cart, set_status
from ..utils import setting, visitor_token

bp = Blueprint("shop", __name__)


@bp.get("/produtos")
def catalog():
    search = request.args.get("q", "").strip()[:120]
    category_slug = request.args.get("categoria", "").strip()[:160]
    sort = request.args.get("ordem", "destaques")
    page = request.args.get("page", 1, type=int)

    query = Product.query.filter(Product.status == "active")
    selected_category = None
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.short_description.ilike(pattern),
                Product.description.ilike(pattern),
            )
        )
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug, is_active=True).first_or_404()
        query = query.filter(Product.category_id == selected_category.id)

    if sort == "recentes":
        query = query.order_by(Product.created_at.desc())
    elif sort == "nome":
        query = query.order_by(Product.name.asc())
    elif sort == "menor-preco":
        query = query.order_by(Product.price.is_(None), Product.price.asc())
    elif sort == "maior-preco":
        query = query.order_by(Product.price.is_(None), Product.price.desc())
    else:
        query = query.order_by(Product.is_featured.desc(), Product.updated_at.desc())

    pagination = query.paginate(page=page, per_page=16, error_out=False)
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()

    db.session.add(
        AnalyticsEvent(
            event_type="catalog_search" if search else "page_view",
            path=request.full_path,
            visitor_token=visitor_token(),
            metadata_json={"q": search, "category": category_slug, "sort": sort},
        )
    )
    db.session.commit()

    return render_template(
        "catalog.html",
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        selected_category=selected_category,
        search=search,
        sort=sort,
    )


@bp.get("/produto/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, status="active").first_or_404()
    product.views += 1
    db.session.add(
        AnalyticsEvent(
            event_type="product_view",
            path=request.path,
            product_id=product.id,
            visitor_token=visitor_token(),
        )
    )
    db.session.commit()
    related = (
        Product.query.filter(
            Product.status == "active",
            Product.category_id == product.category_id,
            Product.id != product.id,
        )
        .order_by(Product.is_featured.desc(), Product.updated_at.desc())
        .limit(4)
        .all()
        if product.category_id
        else []
    )
    return render_template("product.html", product=product, related=related)


@bp.get("/carrinho")
def cart():
    current = get_current_cart(create=False)
    return render_template("cart.html", cart=current)


@bp.post("/carrinho/continuar-whatsapp")
def continue_whatsapp():
    cart = get_current_cart(create=False)
    if not cart or not cart.items:
        flash("Seu carrinho está vazio.", "warning")
        return redirect(url_for("shop.catalog"))
    if cart.status != "open":
        flash("Este carrinho já foi enviado. Adicione novos produtos para gerar outro código.", "info")
        return redirect(url_for("shop.cart"))

    cart.customer_name = request.form.get("customer_name", "").strip()[:150] or None
    cart.customer_company = request.form.get("customer_company", "").strip()[:150] or None
    cart.customer_phone = request.form.get("customer_phone", "").strip()[:50] or None
    cart.customer_email = request.form.get("customer_email", "").strip()[:255] or None
    cart.customer_notes = request.form.get("customer_notes", "").strip()[:4000] or None
    cart.whatsapp_message = build_whatsapp_message(cart)
    set_status(cart, "sent", note="Carrinho enviado pelo visitante via WhatsApp.")
    db.session.add(
        AnalyticsEvent(
            event_type="whatsapp_checkout",
            path=request.path,
            cart_id=cart.id,
            visitor_token=visitor_token(),
            metadata_json={"code": cart.code, "items": cart.item_count},
        )
    )
    db.session.commit()

    whatsapp = "".join(ch for ch in str(setting("whatsapp", "5545998119520")) if ch.isdigit())
    target = f"https://wa.me/{whatsapp}?text={quote(cart.whatsapp_message, safe='')}"
    return redirect(target)
