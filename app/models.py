from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="admin")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    products = db.relationship("Product", back_populates="category", lazy="dynamic")


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True, index=True)
    sku = db.Column(db.String(80), nullable=False, unique=True, index=True)
    short_description = db.Column(db.String(360))
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2))
    compare_at_price = db.Column(db.Numeric(12, 2))
    show_price = db.Column(db.Boolean, nullable=False, default=False)
    min_quantity = db.Column(db.Integer, nullable=False, default=1)
    stock = db.Column(db.Integer)
    track_stock = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_new = db.Column(db.Boolean, nullable=False, default=False)
    personalization_text = db.Column(db.String(255))
    lead_time = db.Column(db.String(120))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    seo_title = db.Column(db.String(180))
    seo_description = db.Column(db.String(320))
    views = db.Column(db.Integer, nullable=False, default=0)

    category = db.relationship("Category", back_populates="products")
    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order, ProductImage.id",
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def primary_image(self):
        if not self.images:
            return None
        return next((image for image in self.images if image.is_primary), self.images[0])

    @property
    def formatted_price(self):
        if self.price is None:
            return None
        return f"R$ {Decimal(self.price):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @property
    def available(self):
        if self.status != "active":
            return False
        if self.track_stock and self.stock is not None:
            return self.stock >= max(self.min_quantity or 1, 1)
        return True


class ProductImage(TimestampMixin, db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    file_path = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    product = db.relationship("Product", back_populates="images")


class Banner(TimestampMixin, db.Model):
    __tablename__ = "banners"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subtitle = db.Column(db.String(360))
    eyebrow = db.Column(db.String(100))
    button_text = db.Column(db.String(80))
    button_url = db.Column(db.String(500))
    image_path = db.Column(db.String(500))
    mobile_image_path = db.Column(db.String(500))
    overlay_strength = db.Column(db.Integer, nullable=False, default=35)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class ClientLogo(TimestampMixin, db.Model):
    __tablename__ = "client_logos"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    website = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class Cart(TimestampMixin, db.Model):
    __tablename__ = "carts"
    __table_args__ = (
        Index("ix_carts_status_updated", "status", "updated_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(80), nullable=False, unique=True, index=True)
    code = db.Column(db.String(20), nullable=False, unique=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="open", index=True)
    customer_name = db.Column(db.String(150))
    customer_company = db.Column(db.String(150))
    customer_phone = db.Column(db.String(50))
    customer_email = db.Column(db.String(255))
    customer_notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)
    whatsapp_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime(timezone=True))
    contacted_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True), index=True)
    source = db.Column(db.String(80), default="site")

    items = db.relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartItem.id",
    )
    history = db.relationship(
        "CartHistory",
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartHistory.created_at.desc()",
    )

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items)

    @property
    def total(self):
        values = [item.subtotal for item in self.items if item.unit_price_snapshot is not None]
        return sum(values, Decimal("0.00"))

    @property
    def has_full_pricing(self):
        return bool(self.items) and all(
            item.show_price_snapshot and item.unit_price_snapshot is not None for item in self.items
        )


class CartItem(TimestampMixin, db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
    )

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), index=True)
    sku_snapshot = db.Column(db.String(80), nullable=False)
    name_snapshot = db.Column(db.String(180), nullable=False)
    image_snapshot = db.Column(db.String(500))
    unit_price_snapshot = db.Column(db.Numeric(12, 2))
    show_price_snapshot = db.Column(db.Boolean, nullable=False, default=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    personalization = db.Column(db.String(500))

    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product")

    @property
    def subtotal(self):
        if self.unit_price_snapshot is None:
            return Decimal("0.00")
        return Decimal(self.unit_price_snapshot) * self.quantity


class CartHistory(db.Model):
    __tablename__ = "cart_history"

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False, index=True)
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    cart = db.relationship("Cart", back_populates="history")
    user = db.relationship("User")


class SiteSetting(TimestampMixin, db.Model):
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), nullable=False, unique=True, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(30), nullable=False, default="text")
    group_name = db.Column(db.String(80), nullable=False, default="general")
    label = db.Column(db.String(160))
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class MediaAsset(TimestampMixin, db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False, unique=True)
    mime_type = db.Column(db.String(120))
    size_bytes = db.Column(db.Integer)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    uploaded_by = db.relationship("User")


class AnalyticsEvent(db.Model):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_event_created", "event_type", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    path = db.Column(db.String(500))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), index=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id", ondelete="SET NULL"), index=True)
    visitor_token = db.Column(db.String(100), index=True)
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    product = db.relationship("Product")
    cart = db.relationship("Cart")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(80))
    entity_id = db.Column(db.String(80))
    details_json = db.Column(db.JSON)
    ip_address = db.Column(db.String(80))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    user = db.relationship("User")
