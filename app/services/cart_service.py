from __future__ import annotations

import secrets
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from flask import session
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Cart, CartHistory, CartItem, Product, utcnow
from ..utils import setting

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _is_expired(expires_at) -> bool:
    if not expires_at:
        return False
    now = utcnow()
    if expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    return expires_at < now


def _new_code() -> str:
    return "PFZ-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(7))


def _create_cart() -> Cart:
    expiry_days = setting("cart_expiry_days", 180)
    for _ in range(12):
        cart = Cart(
            token=secrets.token_urlsafe(36),
            code=_new_code(),
            status="open",
            expires_at=utcnow() + timedelta(days=int(expiry_days)),
        )
        db.session.add(cart)
        try:
            db.session.commit()
            session["cart_token"] = cart.token
            session.permanent = True
            return cart
        except IntegrityError:
            db.session.rollback()
    raise RuntimeError("Não foi possível gerar um código único para o carrinho.")


def get_current_cart(create: bool = False, require_open: bool = False) -> Cart | None:
    token = session.get("cart_token")
    cart = Cart.query.filter_by(token=token).first() if token else None

    if cart and _is_expired(cart.expires_at):
        if cart.status == "open":
            cart.status = "abandoned"
            db.session.commit()
        cart = None
        session.pop("cart_token", None)

    if require_open and cart and cart.status != "open":
        cart = None

    if not cart and create:
        cart = _create_cart()
    return cart


def restore_cart(token: str) -> Cart | None:
    cart = Cart.query.filter_by(token=token).first()
    if not cart or _is_expired(cart.expires_at):
        if cart and cart.status == "open":
            cart.status = "abandoned"
            db.session.commit()
        return None
    session["cart_token"] = cart.token
    session.permanent = True
    return cart


def add_product(product: Product, quantity: int = 1, personalization: str | None = None,
                color_id: str = "", method: str = "") -> Cart:
    colors = product.colors or []
    color = next((c for c in colors if c["id"] == color_id), None)
    if color_id and color is None or colors and color is None:
        raise ValueError("Selecione uma cor disponível para este produto.")
    methods = dict(product.personalization_methods)
    if method and method not in methods:
        raise ValueError("Esta técnica de personalização não está disponível para o produto.")
    if not method and len(methods) == 1:
        method = next(iter(methods))
    elif not method and methods:
        raise ValueError("Escolha como deseja personalizar este produto.")
    personalization = (personalization or "").strip()[:500] or None
    variant_key = hashlib.sha256(json.dumps([color_id, method, personalization], ensure_ascii=False).encode()).hexdigest()
    cart = get_current_cart(create=True, require_open=True)
    if cart is None or cart.status != "open":
        cart = _create_cart()

    quantity = min(max(int(quantity or 1), int(product.min_quantity or 1)), 99999)
    if product.track_stock and product.stock is not None:
        in_cart = sum(item.quantity for item in cart.items if item.product_id == product.id)
        if quantity + in_cart > product.stock:
            raise ValueError("A quantidade total deste produto ultrapassa o estoque disponível.")
    existing = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id, variant_key=variant_key).first()
    image_path = product.primary_image.file_path if product.primary_image else None
    if existing:
        existing.quantity += quantity
        if personalization:
            existing.personalization = personalization.strip()[:500]
    else:
        db.session.add(
            CartItem(
                cart=cart,
                product=product,
                sku_snapshot=product.sku,
                name_snapshot=product.name,
                image_snapshot=image_path,
                unit_price_snapshot=product.price,
                show_price_snapshot=product.show_price,
                quantity=quantity,
                personalization=(personalization or "").strip()[:500] or None,
                variant_key=variant_key,
                color_name_snapshot=color["name"] if color else None,
                color_id_snapshot=color_id or None,
                color_hex_snapshot=color["hex"] if color else None,
                method_snapshot=method or None,
            )
        )
    cart.expires_at = utcnow() + timedelta(days=int(setting("cart_expiry_days", 180)))
    db.session.commit()
    return cart


def update_item(cart: Cart, item_id: int, quantity: int, personalization: str | None = None):
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first_or_404()
    if quantity <= 0:
        db.session.delete(item)
    else:
        minimum = item.product.min_quantity if item.product and item.product.min_quantity else 1
        maximum = 99999
        if item.product and item.product.track_stock and item.product.stock is not None:
            other_quantity = sum(other.quantity for other in cart.items if other.product_id == item.product_id and other.id != item.id)
            maximum = max(item.product.stock - other_quantity, 0)
            if maximum < minimum or quantity > maximum:
                raise ValueError("A quantidade total deste produto ultrapassa o estoque disponível.")
        item.quantity = min(max(quantity, minimum), maximum)
        if personalization is not None:
            new_personalization = str(personalization).strip()[:500] or None
            new_key = hashlib.sha256(json.dumps([item.color_id_snapshot or "", item.method_snapshot or "", new_personalization], ensure_ascii=False).encode()).hexdigest()
            duplicate = CartItem.query.filter(CartItem.cart_id == cart.id, CartItem.product_id == item.product_id,
                                             CartItem.variant_key == new_key, CartItem.id != item.id).first()
            if duplicate:
                raise ValueError("Esta combinação já está no carrinho. Ajuste a quantidade do item existente.")
            item.personalization = new_personalization
            item.variant_key = new_key
    cart.expires_at = utcnow() + timedelta(days=int(setting("cart_expiry_days", 180)))
    db.session.commit()
    return cart


def remove_item(cart: Cart, item_id: int):
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first_or_404()
    db.session.delete(item)
    cart.expires_at = utcnow() + timedelta(days=int(setting("cart_expiry_days", 180)))
    db.session.commit()


def set_status(cart: Cart, status: str, user_id=None, note=None):
    old = cart.status
    if old == status and not note:
        return
    cart.status = status
    if status == "sent" and not cart.sent_at:
        cart.sent_at = utcnow()
    if status == "contacted" and not cart.contacted_at:
        cart.contacted_at = utcnow()
    db.session.add(
        CartHistory(
            cart=cart,
            from_status=old,
            to_status=status,
            note=note,
            user_id=user_id,
        )
    )


def format_brl(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"R$ {Decimal(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_whatsapp_message(cart: Cart) -> str:
    lines = [
        "Olá! Vim pelo site da Presentear Foz e gostaria de solicitar um orçamento.",
        "",
        f"Código do carrinho: {cart.code}",
        "",
        "Itens selecionados:",
    ]
    for item in cart.items:
        line = f"• {item.quantity}x {item.name_snapshot} ({item.sku_snapshot})"
        if item.options_label:
            line += f" — {item.options_label}"
        if item.personalization:
            line += f" — Personalização: {item.personalization}"
        lines.append(line)
    if cart.customer_name:
        lines.extend(["", f"Nome: {cart.customer_name}"])
    if cart.customer_company:
        lines.append(f"Empresa: {cart.customer_company}")
    if cart.customer_notes:
        lines.extend(["", f"Observações: {cart.customer_notes}"])
    lines.extend(["", "A equipe pode localizar todos os detalhes pelo código acima."])
    return "\n".join(lines)
