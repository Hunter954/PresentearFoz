from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import AnalyticsEvent, Product
from ..services.cart_service import (
    add_product,
    get_current_cart,
    remove_item,
    restore_cart,
    update_item,
)
from ..utils import media_url, visitor_token

bp = Blueprint("api", __name__, url_prefix="/api")


def serialize_cart(cart):
    if not cart:
        return {"token": None, "code": None, "status": None, "count": 0, "items": []}
    return {
        "token": cart.token,
        "code": cart.code,
        "status": cart.status,
        "count": cart.item_count,
        "has_full_pricing": cart.has_full_pricing,
        "total": str(cart.total),
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "name": item.name_snapshot,
                "sku": item.sku_snapshot,
                "quantity": item.quantity,
                "personalization": item.personalization,
                "image": media_url(item.image_snapshot),
                "show_price": item.show_price_snapshot,
                "unit_price": str(item.unit_price_snapshot) if item.unit_price_snapshot is not None else None,
                "subtotal": str(item.subtotal),
            }
            for item in cart.items
        ],
    }


@bp.get("/cart")
def cart_summary():
    return jsonify(serialize_cart(get_current_cart(create=False)))


@bp.post("/cart/restore")
def cart_restore():
    payload = request.get_json(silent=True) or request.form
    token = str(payload.get("token", "")).strip()[:120]
    cart = restore_cart(token) if token else None
    if not cart:
        return jsonify({"ok": False, "message": "Carrinho não encontrado ou expirado."}), 404
    return jsonify({"ok": True, "cart": serialize_cart(cart)})


@bp.post("/cart/items")
def cart_add_item():
    payload = request.get_json(silent=True) or request.form
    try:
        product_id = int(payload.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Produto inválido."}), 400
    product = Product.query.filter_by(id=product_id, status="active").first()
    if not product or not product.available:
        return jsonify({"ok": False, "message": "Produto indisponível."}), 404
    try:
        quantity = int(payload.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    personalization = str(payload.get("personalization", "")).strip()
    cart = add_product(product, quantity, personalization)
    db.session.add(
        AnalyticsEvent(
            event_type="add_to_cart",
            product_id=product.id,
            cart_id=cart.id,
            visitor_token=visitor_token(),
            metadata_json={"quantity": quantity},
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "message": "Produto adicionado ao carrinho.", "cart": serialize_cart(cart)})


@bp.patch("/cart/items/<int:item_id>")
def cart_update_item(item_id):
    cart = get_current_cart(create=False)
    if not cart or cart.status != "open":
        return jsonify({"ok": False, "message": "Carrinho não encontrado ou já enviado."}), 404
    payload = request.get_json(silent=True) or request.form
    try:
        quantity = int(payload.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    personalization = payload.get("personalization")
    update_item(cart, item_id, quantity, personalization)
    return jsonify({"ok": True, "cart": serialize_cart(cart)})


@bp.delete("/cart/items/<int:item_id>")
def cart_remove_item(item_id):
    cart = get_current_cart(create=False)
    if not cart or cart.status != "open":
        return jsonify({"ok": False, "message": "Carrinho não encontrado ou já enviado."}), 404
    remove_item(cart, item_id)
    return jsonify({"ok": True, "cart": serialize_cart(cart)})


@bp.get("/search")
def search():
    term = request.args.get("q", "").strip()[:120]
    if len(term) < 2:
        return jsonify([])
    pattern = f"%{term}%"
    products = (
        Product.query.filter(
            Product.status == "active",
            or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)),
        )
        .order_by(Product.is_featured.desc(), Product.name)
        .limit(8)
        .all()
    )
    return jsonify(
        [
            {
                "name": product.name,
                "sku": product.sku,
                "url": f"/produto/{product.slug}",
                "image": media_url(product.primary_image.file_path if product.primary_image else None),
            }
            for product in products
        ]
    )
