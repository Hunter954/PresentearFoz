"""Import the reviewed catalog manifest without deleting existing products."""
import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path

from flask import current_app
from .extensions import db
from .models import Category, Product, ProductImage, MediaAsset
from .product_options import default_colors
from .utils import unique_slug


def normalized_name(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().strip()).casefold()


def import_catalog(manifest_path):
    manifest_path = Path(manifest_path)
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))["products"]
    # Validate every asset before making any database changes.
    for entry in entries:
        source = (manifest_path.parent / entry["image"]).resolve()
        if not source.is_relative_to(manifest_path.parent.resolve()) or not source.is_file():
            raise ValueError(f"Imagem ausente ou inválida: {entry['image']}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Imagem alterada: {entry['image']}")
    category_map = {normalized_name(c.name): c for c in Category.query.all()}
    product_map = {}
    for product in Product.query.all():
        product_map.setdefault(normalized_name(product.name), []).append(product)
    stats = dict(created=0, matched=0, categories_created=0, images_added=0)
    for entry in entries:
        category_key = normalized_name(entry["category"])
        category = category_map.get(category_key)
        if category is None:
            category = Category(name=entry["category"], slug=unique_slug(Category, entry["category"]), is_active=True)
            db.session.add(category)
            db.session.flush()
            category_map[category_key] = category
            stats["categories_created"] += 1
        matches = product_map.get(normalized_name(entry["name"]), [])
        product = Product.query.filter_by(sku=entry["sku"]).first()
        if not product and len(matches) > 1:
            raise ValueError(f"Mais de um produto com o nome {entry['name']}; revise antes de importar.")
        product = product or (matches[0] if matches else None)
        if product is None:
            product = Product(name=entry["name"], slug=unique_slug(Product, entry["name"]),
                              sku=entry["sku"], category=category, status="active", show_price=False,
                              laser_enabled=True, sublimation_enabled=False, colors=default_colors(), min_quantity=1)
            db.session.add(product)
            db.session.flush()
            product_map.setdefault(normalized_name(product.name), []).append(product)
            stats["created"] += 1
        else:
            product.category = category
            stats["matched"] += 1
        source = manifest_path.parent / entry["image"]
        relative_path = f"uploads/catalog/{source.name}"
        destination = Path(current_app.config["UPLOAD_FOLDER"]) / "catalog" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or hashlib.sha256(destination.read_bytes()).hexdigest() != entry["sha256"]:
            shutil.copyfile(source, destination)
        if not MediaAsset.query.filter_by(file_path=relative_path).first():
            db.session.add(MediaAsset(original_name=entry["source_file"], file_name=source.name,
                                      file_path=relative_path, mime_type="image/png", size_bytes=source.stat().st_size))
        if not any(image.file_path == relative_path for image in product.images):
            for old_image in product.images:
                old_image.is_primary = False
            product.images.append(ProductImage(file_path=relative_path, alt_text=product.name,
                                               is_primary=True, sort_order=0))
            stats["images_added"] += 1
        if not category.image_path:
            category.image_path = relative_path
    db.session.commit()
    return stats
