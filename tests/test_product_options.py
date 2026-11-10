from pathlib import Path
import json
import hashlib

import sqlalchemy as sa
from PIL import Image
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Product, Cart, Category, ProductImage
from app.product_options import parse_colors, default_colors
from app.catalog_import import import_catalog
from app.schema_updates import upgrade_product_options


def product_id(app, **options):
    with app.app_context():
        product = Product.query.first()
        for key, value in options.items():
            setattr(product, key, value)
        db.session.commit()
        return product.id


def test_variants_are_separate_and_snapshotted(client, app):
    pid = product_id(app, sublimation_enabled=True)
    payload = dict(product_id=pid, color_id='branco', method='laser', quantity=2)
    assert client.post('/api/cart/items', json=payload).status_code == 200
    client.post('/api/cart/items', json=payload)
    client.post('/api/cart/items', json={**payload, 'color_id': 'preto'})
    response = client.post('/api/cart/items', json={**payload, 'method': 'sublimation'})
    items = response.json['cart']['items']
    assert len(items) == 3
    assert [item['quantity'] for item in items] == [4, 2, 2]
    assert items[2]['options_label'] == 'Branco · Sublimação'
    product_id(app, colors=[], laser_enabled=False, sublimation_enabled=False)
    assert 'Branco · Sublimação' in client.get('/carrinho').text
    client.post('/carrinho/continuar-whatsapp', data={'customer_name': 'Teste'})
    with app.app_context():
        assert 'Branco · Sublimação' in Cart.query.first().whatsapp_message


def test_invalid_or_missing_options_do_not_create_cart(client, app):
    pid = product_id(app)
    for options in ({}, {'color_id': 'inventada'}, {'color_id': 'branco', 'method': 'sublimation'},
                    {'color_id': 'branco', 'method': 'arbitrario'}):
        assert client.post('/api/cart/items', json={'product_id': pid, **options}).status_code == 400
    with app.app_context():
        assert Cart.query.count() == 0
    product_id(app, sublimation_enabled=True)
    assert client.post('/api/cart/items', json={'product_id': pid, 'color_id': 'branco'}).status_code == 400


def test_stock_combines_all_colors(client, app):
    pid = product_id(app, stock=3, track_stock=True)
    first = client.post('/api/cart/items', json={'product_id': pid, 'color_id': 'branco', 'quantity': 2})
    assert first.status_code == 200
    assert client.post('/api/cart/items', json={'product_id': pid, 'color_id': 'preto', 'quantity': 2}).status_code == 400
    second = client.post('/api/cart/items', json={'product_id': pid, 'color_id': 'preto', 'quantity': 1})
    assert second.status_code == 200
    item = second.json['cart']['items'][1]['id']
    assert client.patch(f'/api/cart/items/{item}', json={'quantity': 2}).status_code == 400


def test_admin_can_save_options_and_remove_all_colors(client, app):
    pid = product_id(app)
    assert client.get(f'/admin/produtos/{pid}/editar').status_code == 302
    client.post('/admin/login', data={'email': 'admin@presentearfoz.com.br', 'password': 'TroqueEstaSenha123!'})
    assert client.get(f'/admin/produtos/{pid}/editar').status_code == 200
    data = MultiDict([('name', 'Caneca de teste'), ('sku', 'TEST-001'), ('status', 'active'),
                      ('options_present', '1'), ('sublimation_enabled', 'on'),
                      ('color_id', ''), ('color_name', 'Verde-oliva'), ('color_hex', '#778855')])
    assert client.post(f'/admin/produtos/{pid}/editar', data=data).status_code == 302
    with app.app_context():
        product = db.session.get(Product, pid)
        assert not product.laser_enabled and product.sublimation_enabled
        assert product.colors[0]['name'] == 'Verde-oliva'
        slug = product.slug
    html = client.get(f'/produto/{slug}').text
    assert 'Verde-oliva' in html and 'value="sublimation"' in html and 'value="laser"' not in html
    for key in ['color_id', 'color_name', 'color_hex']:
        del data[key]
    client.post(f'/admin/produtos/{pid}/editar', data=data)
    with app.app_context():
        assert db.session.get(Product, pid).colors == []
    assert client.post('/api/cart/items', json={'product_id': pid, 'method': 'sublimation'}).status_code == 200


def test_color_validation_and_stable_ids():
    import pytest
    with pytest.raises(ValueError):
        parse_colors(MultiDict([('color_id', 'branco'), ('color_name', 'Branco'), ('color_hex', 'red;display:none')]), default_colors())
    colors = parse_colors(MultiDict([('color_id', 'branco'), ('color_name', 'Branco gelo'), ('color_hex', '#EEEEEE')]), default_colors())
    assert colors[0]['id'] == 'branco'


def test_import_is_idempotent_preserves_prices_and_admin_options(app, tmp_path):
    image = tmp_path / 'photo.png'
    Image.new('RGB', (8, 8), 'white').save(image)
    manifest = tmp_path / 'products.json'
    manifest.write_text(json.dumps({'products': [{'name': 'CANECA NOVA', 'category': 'CANECA', 'sku': 'IMPORT-001',
        'image': 'photo.png', 'sha256': hashlib.sha256(image.read_bytes()).hexdigest(), 'source_file': 'CANECA NOVA.png'}]}), encoding='utf-8')
    with app.app_context():
        app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
        first = import_catalog(manifest)
        assert first['created'] == first['images_added'] == first['categories_created'] == 1
        product = Product.query.filter_by(sku='IMPORT-001').one()
        product.price = 123
        product.colors = []
        product.laser_enabled = False
        product.sublimation_enabled = True
        db.session.commit()
        second = import_catalog(manifest)
        assert second['created'] == second['images_added'] == second['categories_created'] == 0
        assert product.price == 123 and product.colors == [] and not product.laser_enabled
        assert product.sublimation_enabled


def test_legacy_upgrade_keeps_cart_and_does_not_reset_choices(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()
        with db.engine.begin() as connection:
            connection.execute(sa.text('CREATE TABLE products (id INTEGER PRIMARY KEY, name VARCHAR(180))'))
            connection.execute(sa.text("INSERT INTO products (id, name) VALUES (1, 'Existing')"))
            connection.execute(sa.text('CREATE TABLE cart_items (id INTEGER PRIMARY KEY, cart_id INTEGER, product_id INTEGER, quantity INTEGER, CONSTRAINT uq_cart_product UNIQUE(cart_id, product_id))'))
            connection.execute(sa.text('INSERT INTO cart_items VALUES (1, 1, 1, 3)'))
        upgrade_product_options()
        with db.engine.begin() as connection:
            assert connection.execute(sa.text('SELECT quantity FROM cart_items')).scalar() == 3
            assert connection.execute(sa.text('SELECT laser_enabled FROM products')).scalar() == 1
            connection.execute(sa.text("UPDATE products SET colors='[]', laser_enabled=0"))
        upgrade_product_options()
        with db.engine.begin() as connection:
            assert connection.execute(sa.text('SELECT colors FROM products')).scalar() == '[]'
            assert connection.execute(sa.text('SELECT laser_enabled FROM products')).scalar() == 0
            connection.execute(sa.text("INSERT INTO cart_items (id,cart_id,product_id,quantity,variant_key) VALUES (2,1,1,1,'other')"))
