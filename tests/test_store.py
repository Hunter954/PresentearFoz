from app.models import Cart, Product


def test_home_and_catalog_load(client):
    assert client.get('/').status_code == 200
    assert client.get('/produtos').status_code == 200


def test_cart_gets_code_and_persists(client, app):
    with app.app_context():
        product = Product.query.filter_by(status='active').first()
        product_id = product.id

    response = client.post('/api/cart/items', json={'product_id': product_id, 'quantity': 2})
    assert response.status_code == 200
    data = response.get_json()['cart']
    assert data['code'].startswith('PFZ-')
    assert data['count'] == 2

    again = client.get('/api/cart').get_json()
    assert again['token'] == data['token']
    assert again['code'] == data['code']


def test_whatsapp_checkout_marks_cart_sent(client, app):
    with app.app_context():
        product_id = Product.query.filter_by(status='active').first().id
    client.post('/api/cart/items', json={'product_id': product_id, 'quantity': 1})
    response = client.post('/carrinho/continuar-whatsapp', data={'customer_name': 'Cliente Teste'})
    assert response.status_code == 302
    assert response.location.startswith('https://wa.me/')
    with app.app_context():
        cart = Cart.query.first()
        assert cart.status == 'sent'
        assert cart.customer_name == 'Cliente Teste'
        assert cart.code in cart.whatsapp_message


def test_admin_login(client):
    response = client.post('/admin/login', data={
        'email': 'admin@presentearfoz.com.br',
        'password': 'TroqueEstaSenha123!'
    })
    assert response.status_code == 302
    dashboard = client.get('/admin/')
    assert dashboard.status_code == 200
