from __future__ import annotations

import csv
import io
import re
from functools import wraps
from urllib.parse import urlparse
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    AnalyticsEvent,
    AuditLog,
    Banner,
    Cart,
    CartHistory,
    CartItem,
    Category,
    ClientLogo,
    MediaAsset,
    Product,
    ProductImage,
    SiteSetting,
    User,
    utcnow,
)
from ..services.cart_service import set_status
from ..utils import audit, set_setting, setting, unique_slug, upload_image

bp = Blueprint("admin", __name__, url_prefix="/admin")

CART_STATUSES = {
    "open": "Aberto",
    "sent": "Enviado pelo WhatsApp",
    "contacted": "Em atendimento",
    "quoted": "Orçamento enviado",
    "closed": "Fechado",
    "lost": "Não convertido",
    "abandoned": "Abandonado",
}
PRODUCT_STATUSES = {
    "active": "Ativo",
    "draft": "Rascunho",
    "archived": "Arquivado",
}


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _bool(name: str) -> bool:
    return request.form.get(name) in {"1", "true", "on", "yes", "sim"}


def _int(name: str, default=0, minimum=None):
    try:
        value = int(request.form.get(name, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    return value


def _decimal(name: str):
    value = request.form.get(name, "").strip().replace("R$", "").replace(" ", "")
    if not value:
        return None
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"Valor inválido no campo {name}.")


def _safe_link(value: str | None, *, allow_relative: bool = True) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if allow_relative and value.startswith("/") and not value.startswith("//"):
        return value[:500]
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value[:500]
    raise ValueError("Informe um link válido começando com https:// ou uma rota interna começando com /.")


def _apply_product_form(product: Product):
    product.name = request.form.get("name", "").strip()[:180]
    product.slug = unique_slug(Product, request.form.get("slug") or product.name, product.id)
    product.sku = request.form.get("sku", "").strip().upper()[:80]
    product.short_description = request.form.get("short_description", "").strip()[:360] or None
    product.description = request.form.get("description", "").strip() or None
    product.price = _decimal("price")
    product.compare_at_price = _decimal("compare_at_price")
    product.show_price = _bool("show_price")
    product.min_quantity = _int("min_quantity", 1, 1)
    product.track_stock = _bool("track_stock")
    stock_raw = request.form.get("stock", "").strip()
    product.stock = max(int(stock_raw), 0) if stock_raw else None
    product.status = request.form.get("status", "draft") if request.form.get("status") in PRODUCT_STATUSES else "draft"
    product.is_featured = _bool("is_featured")
    product.is_new = _bool("is_new")
    product.personalization_text = request.form.get("personalization_text", "").strip()[:255] or None
    product.lead_time = request.form.get("lead_time", "").strip()[:120] or None
    product.category_id = request.form.get("category_id", type=int) or None
    product.seo_title = request.form.get("seo_title", "").strip()[:180] or None
    product.seo_description = request.form.get("seo_description", "").strip()[:320] or None

    if not product.name or not product.sku:
        raise ValueError("Nome e SKU são obrigatórios.")


@bp.get("/")
@login_required
def dashboard():
    now = utcnow()
    since_30 = now - timedelta(days=30)
    total_products = Product.query.filter(Product.status != "archived").count()
    active_products = Product.query.filter_by(status="active").count()
    open_carts = Cart.query.filter(Cart.status.in_(["open", "sent", "contacted", "quoted"])).count()
    sent_30 = Cart.query.filter(Cart.sent_at >= since_30).count()
    converted_30 = Cart.query.filter(Cart.status == "closed", Cart.updated_at >= since_30).count()
    views_30 = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type.in_(["page_view", "product_view"]),
        AnalyticsEvent.created_at >= since_30,
    ).count()

    recent_carts = Cart.query.order_by(Cart.updated_at.desc()).limit(10).all()
    top_products = (
        db.session.query(Product, func.count(AnalyticsEvent.id).label("event_count"))
        .outerjoin(
            AnalyticsEvent,
            (AnalyticsEvent.product_id == Product.id)
            & (AnalyticsEvent.event_type == "add_to_cart")
            & (AnalyticsEvent.created_at >= since_30),
        )
        .group_by(Product.id)
        .order_by(func.count(AnalyticsEvent.id).desc(), Product.views.desc())
        .limit(8)
        .all()
    )
    status_counts = dict(
        db.session.query(Cart.status, func.count(Cart.id)).group_by(Cart.status).all()
    )
    return render_template(
        "admin/dashboard.html",
        total_products=total_products,
        active_products=active_products,
        open_carts=open_carts,
        sent_30=sent_30,
        converted_30=converted_30,
        views_30=views_30,
        recent_carts=recent_carts,
        top_products=top_products,
        status_counts=status_counts,
        cart_statuses=CART_STATUSES,
    )


@bp.get("/produtos")
@login_required
def products():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    category_id = request.args.get("category_id", type=int)
    query = Product.query
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if status in PRODUCT_STATUSES:
        query = query.filter(Product.status == status)
    if category_id:
        query = query.filter(Product.category_id == category_id)
    pagination = query.order_by(Product.updated_at.desc()).paginate(page=page, per_page=25, error_out=False)
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin/products.html",
        products=pagination.items,
        pagination=pagination,
        categories=categories,
        product_statuses=PRODUCT_STATUSES,
        search=search,
        status=status,
        category_id=category_id,
    )


@bp.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def product_new():
    product = Product(status="draft", min_quantity=1, show_price=bool(setting("show_prices_default", False)))
    if request.method == "POST":
        try:
            _apply_product_form(product)
            if Product.query.filter_by(sku=product.sku).first():
                raise ValueError("Já existe um produto com este SKU.")
            db.session.add(product)
            db.session.flush()
            files = request.files.getlist("images")
            for index, file in enumerate(files):
                path = upload_image(file, f"products/{product.id}")
                if path:
                    db.session.add(
                        ProductImage(
                            product=product,
                            file_path=path,
                            alt_text=product.name,
                            sort_order=index,
                            is_primary=index == 0,
                        )
                    )
            audit("product_create", "product", product.id, {"sku": product.sku})
            db.session.commit()
            flash("Produto criado com sucesso.", "success")
            return redirect(url_for("admin.product_edit", product_id=product.id))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template(
        "admin/product_form.html",
        product=product,
        categories=categories,
        product_statuses=PRODUCT_STATUSES,
        page_title="Novo produto",
    )


@bp.route("/produtos/<int:product_id>/editar", methods=["GET", "POST"])
@login_required
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        try:
            old_sku = product.sku
            _apply_product_form(product)
            duplicate = Product.query.filter(Product.sku == product.sku, Product.id != product.id).first()
            if duplicate:
                raise ValueError("Já existe outro produto com este SKU.")
            files = request.files.getlist("images")
            start = len(product.images)
            for index, file in enumerate(files, start=start):
                path = upload_image(file, f"products/{product.id}")
                if path:
                    db.session.add(
                        ProductImage(
                            product=product,
                            file_path=path,
                            alt_text=product.name,
                            sort_order=index,
                            is_primary=not product.images and index == 0,
                        )
                    )
            audit("product_update", "product", product.id, {"from_sku": old_sku, "sku": product.sku})
            db.session.commit()
            flash("Produto atualizado.", "success")
            return redirect(url_for("admin.product_edit", product_id=product.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin/product_form.html",
        product=product,
        categories=categories,
        product_statuses=PRODUCT_STATUSES,
        page_title=f"Editar {product.name}",
    )


@bp.post("/produtos/<int:product_id>/arquivar")
@login_required
def product_archive(product_id):
    product = Product.query.get_or_404(product_id)
    product.status = "archived"
    audit("product_archive", "product", product.id)
    db.session.commit()
    flash("Produto arquivado.", "success")
    return redirect(url_for("admin.products"))


@bp.post("/produtos/<int:product_id>/imagens/<int:image_id>/principal")
@login_required
def product_image_primary(product_id, image_id):
    product = Product.query.get_or_404(product_id)
    image = ProductImage.query.filter_by(id=image_id, product_id=product.id).first_or_404()
    ProductImage.query.filter_by(product_id=product.id).update({"is_primary": False})
    image.is_primary = True
    audit("product_image_primary", "product", product.id, {"image_id": image.id})
    db.session.commit()
    flash("Imagem principal atualizada.", "success")
    return redirect(url_for("admin.product_edit", product_id=product.id))


@bp.post("/produtos/<int:product_id>/imagens/<int:image_id>/excluir")
@login_required
def product_image_delete(product_id, image_id):
    product = Product.query.get_or_404(product_id)
    image = ProductImage.query.filter_by(id=image_id, product_id=product.id).first_or_404()
    was_primary = image.is_primary
    next_image = (
        ProductImage.query.filter(
            ProductImage.product_id == product.id, ProductImage.id != image.id
        )
        .order_by(ProductImage.sort_order, ProductImage.id)
        .first()
    )
    db.session.delete(image)
    if was_primary and next_image:
        next_image.is_primary = True
    audit("product_image_delete", "product", product.id, {"image_id": image_id})
    db.session.commit()
    flash("Imagem removida do produto.", "success")
    return redirect(url_for("admin.product_edit", product_id=product.id))


@bp.get("/produtos/exportar.csv")
@login_required
def products_export():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "sku", "nome", "categoria", "status", "preco", "mostrar_preco",
        "quantidade_minima", "destaque", "novo", "descricao_curta"
    ])
    for product in Product.query.order_by(Product.id).all():
        writer.writerow([
            product.sku,
            product.name,
            product.category.name if product.category else "",
            product.status,
            product.price or "",
            "sim" if product.show_price else "nao",
            product.min_quantity,
            "sim" if product.is_featured else "nao",
            "sim" if product.is_new else "nao",
            product.short_description or "",
        ])
    audit("products_export", "product")
    db.session.commit()
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=produtos-presentearfoz.csv"},
    )


@bp.post("/produtos/importar")
@login_required
def products_import():
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("Selecione um arquivo CSV.", "danger")
        return redirect(url_for("admin.products"))
    try:
        content = file.stream.read().decode("utf-8-sig")
        rows = csv.DictReader(io.StringIO(content))
        count = 0
        for row in rows:
            sku = (row.get("sku") or "").strip().upper()
            name = (row.get("nome") or "").strip()
            if not sku or not name:
                continue
            product = Product.query.filter_by(sku=sku).first() or Product(sku=sku)
            product.name = name
            product.slug = unique_slug(Product, name, product.id)
            category_name = (row.get("categoria") or "").strip()
            if category_name:
                category = Category.query.filter(func.lower(Category.name) == category_name.lower()).first()
                if not category:
                    category = Category(name=category_name, slug=unique_slug(Category, category_name), is_active=True)
                    db.session.add(category)
                    db.session.flush()
                product.category = category
            product.status = row.get("status") if row.get("status") in PRODUCT_STATUSES else "active"
            price = (row.get("preco") or "").strip().replace("R$", "").replace(" ", "")
            if "," in price:
                price = price.replace(".", "").replace(",", ".")
            product.price = Decimal(price) if price else None
            product.show_price = str(row.get("mostrar_preco", "")).lower() in {"sim", "1", "true"}
            product.min_quantity = max(int(row.get("quantidade_minima") or 1), 1)
            product.is_featured = str(row.get("destaque", "")).lower() in {"sim", "1", "true"}
            product.is_new = str(row.get("novo", "")).lower() in {"sim", "1", "true"}
            product.short_description = (row.get("descricao_curta") or "").strip()[:360] or None
            db.session.add(product)
            count += 1
        audit("products_import", "product", details={"count": count})
        db.session.commit()
        flash(f"Importação concluída: {count} produto(s) processado(s).", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Falha na importação: {exc}", "danger")
    return redirect(url_for("admin.products"))


@bp.route("/categorias", methods=["GET", "POST"])
@login_required
def categories():
    edit_id = request.args.get("editar", type=int)
    edit_category = Category.query.get(edit_id) if edit_id else None
    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        category = Category.query.get(category_id) if category_id else Category()
        if not category:
            category = Category()
        category.name = request.form.get("name", "").strip()[:120]
        if not category.name:
            flash("Informe o nome da categoria.", "danger")
            return redirect(url_for("admin.categories"))
        category.slug = unique_slug(Category, request.form.get("slug") or category.name, category.id)
        category.description = request.form.get("description", "").strip() or None
        category.is_active = _bool("is_active")
        category.is_featured = _bool("is_featured")
        category.sort_order = _int("sort_order", 0)
        try:
            path = upload_image(request.files.get("image"), "categories")
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.categories", editar=category.id) if category.id else url_for("admin.categories"))
        if path:
            category.image_path = path
        db.session.add(category)
        db.session.flush()
        audit("category_save", "category", category.id)
        db.session.commit()
        flash("Categoria salva.", "success")
        return redirect(url_for("admin.categories"))
    items = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template("admin/categories.html", categories=items, edit_category=edit_category)


@bp.post("/categorias/<int:category_id>/excluir")
@login_required
def category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products.count():
        flash("Esta categoria possui produtos. Arquive-a em vez de excluir.", "warning")
    else:
        audit("category_delete", "category", category.id)
        db.session.delete(category)
        db.session.commit()
        flash("Categoria excluída.", "success")
    return redirect(url_for("admin.categories"))


@bp.route("/banners", methods=["GET", "POST"])
@login_required
def banners():
    edit_id = request.args.get("editar", type=int)
    edit_banner = Banner.query.get(edit_id) if edit_id else None
    if request.method == "POST":
        banner_id = request.form.get("banner_id", type=int)
        banner = Banner.query.get(banner_id) if banner_id else Banner()
        if not banner:
            banner = Banner()
        banner.eyebrow = request.form.get("eyebrow", "").strip()[:100] or None
        banner.title = request.form.get("title", "").strip()[:180]
        banner.subtitle = request.form.get("subtitle", "").strip()[:360] or None
        banner.button_text = request.form.get("button_text", "").strip()[:80] or None
        try:
            banner.button_url = _safe_link(request.form.get("button_url"), allow_relative=True)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.banners", editar=banner.id) if banner.id else url_for("admin.banners"))
        banner.overlay_strength = min(max(_int("overlay_strength", 35), 0), 90)
        banner.is_active = _bool("is_active")
        banner.sort_order = _int("sort_order", 0)
        try:
            image_path = upload_image(request.files.get("image"), "banners")
            mobile_path = upload_image(request.files.get("mobile_image"), "banners/mobile")
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.banners", editar=banner.id) if banner.id else url_for("admin.banners"))
        if image_path:
            banner.image_path = image_path
        if mobile_path:
            banner.mobile_image_path = mobile_path
        if not banner.title:
            flash("Informe o título do banner.", "danger")
            return redirect(url_for("admin.banners"))
        db.session.add(banner)
        db.session.flush()
        audit("banner_save", "banner", banner.id)
        db.session.commit()
        flash("Banner salvo.", "success")
        return redirect(url_for("admin.banners"))
    items = Banner.query.order_by(Banner.sort_order, Banner.id).all()
    return render_template("admin/banners.html", banners=items, edit_banner=edit_banner)


@bp.post("/banners/<int:banner_id>/excluir")
@login_required
def banner_delete(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    audit("banner_delete", "banner", banner.id)
    db.session.delete(banner)
    db.session.commit()
    flash("Banner excluído.", "success")
    return redirect(url_for("admin.banners"))


@bp.route("/clientes", methods=["GET", "POST"])
@login_required
def clients():
    edit_id = request.args.get("editar", type=int)
    edit_client = ClientLogo.query.get(edit_id) if edit_id else None
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        client = ClientLogo.query.get(client_id) if client_id else ClientLogo()
        if not client:
            client = ClientLogo()
        client.name = request.form.get("name", "").strip()[:150]
        try:
            client.website = _safe_link(request.form.get("website"), allow_relative=False)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.clients", editar=client.id) if client.id else url_for("admin.clients"))
        client.is_active = _bool("is_active")
        client.sort_order = _int("sort_order", 0)
        try:
            path = upload_image(request.files.get("image"), "clients")
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.clients", editar=client.id) if client.id else url_for("admin.clients"))
        if path:
            client.image_path = path
        if not client.name or not client.image_path:
            flash("Nome e imagem são obrigatórios.", "danger")
            return redirect(url_for("admin.clients"))
        db.session.add(client)
        db.session.flush()
        audit("client_save", "client", client.id)
        db.session.commit()
        flash("Cliente salvo.", "success")
        return redirect(url_for("admin.clients"))
    items = ClientLogo.query.order_by(ClientLogo.sort_order, ClientLogo.name).all()
    return render_template("admin/clients.html", clients=items, edit_client=edit_client)


@bp.post("/clientes/<int:client_id>/excluir")
@login_required
def client_delete(client_id):
    client = ClientLogo.query.get_or_404(client_id)
    audit("client_delete", "client", client.id)
    db.session.delete(client)
    db.session.commit()
    flash("Cliente excluído.", "success")
    return redirect(url_for("admin.clients"))


@bp.get("/carrinhos")
@login_required
def carts():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = Cart.query
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Cart.code.ilike(pattern),
                Cart.customer_name.ilike(pattern),
                Cart.customer_company.ilike(pattern),
                Cart.customer_phone.ilike(pattern),
            )
        )
    if status in CART_STATUSES:
        query = query.filter(Cart.status == status)
    pagination = query.order_by(Cart.updated_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template(
        "admin/carts.html",
        carts=pagination.items,
        pagination=pagination,
        cart_statuses=CART_STATUSES,
        search=search,
        status=status,
    )


@bp.route("/carrinhos/<int:cart_id>", methods=["GET", "POST"])
@login_required
def cart_detail(cart_id):
    cart = Cart.query.get_or_404(cart_id)
    if request.method == "POST":
        new_status = request.form.get("status", cart.status)
        if new_status not in CART_STATUSES:
            new_status = cart.status
        note = request.form.get("history_note", "").strip()[:500] or None
        set_status(cart, new_status, current_user.id, note)
        cart.admin_notes = request.form.get("admin_notes", "").strip() or None
        cart.customer_name = request.form.get("customer_name", "").strip()[:150] or None
        cart.customer_company = request.form.get("customer_company", "").strip()[:150] or None
        cart.customer_phone = request.form.get("customer_phone", "").strip()[:50] or None
        cart.customer_email = request.form.get("customer_email", "").strip()[:255] or None
        audit("cart_update", "cart", cart.id, {"status": new_status})
        db.session.commit()
        flash("Carrinho atualizado.", "success")
        return redirect(url_for("admin.cart_detail", cart_id=cart.id))
    return render_template("admin/cart_detail.html", cart=cart, cart_statuses=CART_STATUSES)


@bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
@roles_required("admin", "superadmin")
def settings():
    if request.method == "POST":
        rows = SiteSetting.query.order_by(SiteSetting.group_name, SiteSetting.sort_order).all()
        for row in rows:
            if row.value_type == "bool":
                value = "true" if request.form.get(row.key) else "false"
            else:
                value = request.form.get(row.key, "").strip()
            if row.value_type == "color" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                flash(f"Cor inválida em {row.label or row.key}.", "danger")
                return redirect(url_for("admin.settings"))
            if row.value_type == "int":
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    flash(f"Número inválido em {row.label or row.key}.", "danger")
                    return redirect(url_for("admin.settings"))
                if row.key == "cart_expiry_days":
                    number = min(max(number, 14), 730)
                value = str(number)
            set_setting(row.key, value)
        audit("settings_update", "settings")
        db.session.commit()
        flash("Configurações atualizadas.", "success")
        return redirect(url_for("admin.settings"))
    rows = SiteSetting.query.order_by(SiteSetting.group_name, SiteSetting.sort_order, SiteSetting.id).all()
    groups = {}
    for row in rows:
        groups.setdefault(row.group_name, []).append(row)
    return render_template("admin/settings.html", groups=groups)


@bp.route("/usuarios", methods=["GET", "POST"])
@login_required
@roles_required("superadmin")
def users():
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        user = User.query.get(user_id) if user_id else User()
        if not user:
            user = User()
        user.name = request.form.get("name", "").strip()[:120]
        user.email = request.form.get("email", "").strip().lower()[:255]
        user.role = request.form.get("role", "admin") if request.form.get("role") in {"admin", "manager", "superadmin"} else "admin"
        requested_active = _bool("is_active")
        if user.id and user.id == current_user.id and not requested_active:
            flash("Você não pode desativar o próprio usuário enquanto está conectado.", "danger")
            return redirect(url_for("admin.users", editar=user.id))
        user.is_active = requested_active
        password = request.form.get("password", "")
        if password:
            if len(password) < 8:
                flash("A senha deve ter pelo menos 8 caracteres.", "danger")
                return redirect(url_for("admin.users"))
            user.set_password(password)
        elif not user.id:
            flash("Informe uma senha para o novo usuário.", "danger")
            return redirect(url_for("admin.users"))
        if not user.name or not user.email:
            flash("Nome e e-mail são obrigatórios.", "danger")
            return redirect(url_for("admin.users"))
        duplicate = User.query.filter(User.email == user.email, User.id != user.id).first()
        if duplicate:
            flash("Já existe um usuário com este e-mail.", "danger")
            return redirect(url_for("admin.users"))
        db.session.add(user)
        db.session.flush()
        audit("user_save", "user", user.id)
        db.session.commit()
        flash("Usuário salvo.", "success")
        return redirect(url_for("admin.users"))
    edit_id = request.args.get("editar", type=int)
    edit_user = User.query.get(edit_id) if edit_id else None
    return render_template("admin/users.html", users=User.query.order_by(User.name).all(), edit_user=edit_user)


@bp.get("/midia")
@login_required
def media():
    page = request.args.get("page", 1, type=int)
    pagination = MediaAsset.query.order_by(MediaAsset.created_at.desc()).paginate(page=page, per_page=36, error_out=False)
    return render_template("admin/media.html", assets=pagination.items, pagination=pagination)


@bp.post("/midia/<int:asset_id>/excluir")
@login_required
def media_delete(asset_id):
    asset = MediaAsset.query.get_or_404(asset_id)
    in_use = (
        ProductImage.query.filter_by(file_path=asset.file_path).first()
        or Category.query.filter_by(image_path=asset.file_path).first()
        or Banner.query.filter(
            or_(Banner.image_path == asset.file_path, Banner.mobile_image_path == asset.file_path)
        ).first()
        or ClientLogo.query.filter_by(image_path=asset.file_path).first()
    )
    if in_use:
        flash("Esta mídia está sendo usada no site. Remova-a do produto, categoria, banner ou cliente antes de excluir.", "warning")
        return redirect(url_for("admin.media"))

    path = current_app.config["UPLOAD_FOLDER"]
    absolute = None
    if asset.file_path.startswith("uploads/"):
        from pathlib import Path
        absolute = Path(path) / asset.file_path.removeprefix("uploads/")
    if absolute and absolute.exists():
        try:
            absolute.unlink()
        except OSError:
            pass
    audit("media_delete", "media", asset.id)
    db.session.delete(asset)
    db.session.commit()
    flash("Arquivo removido.", "success")
    return redirect(url_for("admin.media"))


@bp.get("/auditoria")
@login_required
@roles_required("admin", "superadmin")
def audit_logs():
    page = request.args.get("page", 1, type=int)
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/audit.html", logs=pagination.items, pagination=pagination)
