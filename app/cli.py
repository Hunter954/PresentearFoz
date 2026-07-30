from __future__ import annotations

import click
from flask import current_app

from .extensions import db
from .models import Banner, Category, Product, SiteSetting, User
from .utils import set_setting, unique_slug


DEFAULT_SETTINGS = [
    ("company_name", "Presentear Foz", "text", "general", "Nome da empresa", 10),
    ("whatsapp", "5545998119520", "text", "contact", "WhatsApp (somente números)", 10),
    ("whatsapp_display", "(45) 99811-9520", "text", "contact", "WhatsApp para exibição", 20),
    ("instagram", "presentearfoz", "text", "contact", "Instagram", 30),
    ("email", "", "text", "contact", "E-mail", 40),
    ("address", "Foz do Iguaçu - PR", "text", "contact", "Localização", 50),
    ("primary_color", "#5F3B73", "color", "visual", "Cor principal", 10),
    ("accent_color", "#FFC82E", "color", "visual", "Cor de destaque", 20),
    ("hero_title", "Presentes que viram memória. Brindes que fortalecem marcas.", "text", "home", "Título principal", 10),
    ("hero_subtitle", "Personalização para pessoas, empresas e momentos especiais em Foz do Iguaçu.", "textarea", "home", "Subtítulo principal", 20),
    ("home_about_title", "Personalização feita para encantar", "text", "home", "Título institucional", 30),
    ("home_about_text", "Canecas, quadros, térmicos, camisetas e brindes corporativos produzidos com atenção aos detalhes e atendimento próximo.", "textarea", "home", "Texto institucional", 40),
    ("cart_expiry_days", "180", "int", "commerce", "Dias para manter o carrinho", 10),
    ("show_clients", "true", "bool", "home", "Exibir clientes", 50),
    ("show_prices_default", "false", "bool", "commerce", "Mostrar preços por padrão", 20),
    ("footer_text", "Presentes personalizados e gravação a laser em Foz do Iguaçu.", "textarea", "general", "Texto do rodapé", 20),
]

DEMO_CATEGORIES = [
    ("Canecas", "Canecas personalizadas para presentear ou divulgar sua marca."),
    ("Térmicos", "Copos, garrafas e itens térmicos personalizados."),
    ("Quadros", "Quadros e peças decorativas feitas sob medida."),
    ("Camisetas", "Camisetas personalizadas para eventos, equipes e presentes."),
    ("Brindes corporativos", "Soluções personalizadas para empresas e campanhas."),
    ("Gravação a laser", "Produtos com gravação precisa e acabamento durável."),
]

DEMO_PRODUCTS = [
    ("Caneca personalizada", "PFZ-CAN-001", "Canecas", "Personalize com nome, foto, frase ou identidade da sua empresa."),
    ("Copo térmico personalizado", "PFZ-TER-001", "Térmicos", "Copo térmico com personalização para presentes e ações corporativas."),
    ("Garrafa térmica com gravação", "PFZ-TER-002", "Térmicos", "Gravação a laser de nomes, logos e mensagens especiais."),
    ("Quadro personalizado", "PFZ-QUA-001", "Quadros", "Uma lembrança única criada a partir da sua ideia."),
    ("Camiseta personalizada", "PFZ-CAM-001", "Camisetas", "Estampas para eventos, equipes, empresas e ocasiões especiais."),
    ("Kit corporativo personalizado", "PFZ-COR-001", "Brindes corporativos", "Monte um kit exclusivo para clientes, colaboradores ou eventos."),
    ("Chaveiro com gravação a laser", "PFZ-LAS-001", "Gravação a laser", "Pequeno no tamanho e marcante nos detalhes."),
    ("Placa comemorativa personalizada", "PFZ-LAS-002", "Gravação a laser", "Placas e homenagens com acabamento profissional."),
]


def bootstrap_database(app=None):
    if current_app.config.get("AUTO_CREATE_DB", True):
        db.create_all()

    for key, value, value_type, group, label, sort_order in DEFAULT_SETTINGS:
        if not SiteSetting.query.filter_by(key=key).first():
            set_setting(
                key,
                value,
                value_type=value_type,
                group_name=group,
                label=label,
                sort_order=sort_order,
            )

    admin_email = current_app.config["ADMIN_EMAIL"].strip().lower()
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(name="Administrador", email=admin_email, role="superadmin")
        admin.set_password(current_app.config["ADMIN_PASSWORD"])
        db.session.add(admin)

    if current_app.config.get("SEED_DEMO"):
        categories = {}
        for order, (name, description) in enumerate(DEMO_CATEGORIES, start=1):
            category = Category.query.filter_by(name=name).first()
            if not category:
                category = Category(
                    name=name,
                    slug=unique_slug(Category, name),
                    description=description,
                    is_active=True,
                    is_featured=True,
                    sort_order=order,
                )
                db.session.add(category)
                db.session.flush()
            categories[name] = category

        if Product.query.count() == 0:
            for order, (name, sku, category_name, short_description) in enumerate(DEMO_PRODUCTS, start=1):
                db.session.add(
                    Product(
                        name=name,
                        slug=unique_slug(Product, name),
                        sku=sku,
                        category=categories[category_name],
                        short_description=short_description,
                        description=short_description,
                        show_price=False,
                        min_quantity=1,
                        status="active",
                        is_featured=order <= 6,
                        is_new=order <= 3,
                        personalization_text="Envie sua arte, nome, frase ou logo pelo WhatsApp após solicitar o orçamento.",
                    )
                )

        if Banner.query.count() == 0:
            db.session.add(
                Banner(
                    eyebrow="PRESENTES PERSONALIZADOS EM FOZ",
                    title="Sua ideia transformada em um presente único",
                    subtitle="Escolha os produtos, monte seu carrinho e envie o código direto para nossa equipe no WhatsApp.",
                    button_text="Ver produtos",
                    button_url="/produtos",
                    is_active=True,
                    sort_order=1,
                )
            )

    db.session.commit()


def register_commands(app):
    @app.cli.command("bootstrap")
    def bootstrap_command():
        """Cria tabelas, configurações iniciais e usuário administrador."""
        bootstrap_database(app)
        click.echo("Bootstrap concluído.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(name, email, password):
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            raise click.ClickException("Já existe um usuário com este e-mail.")
        user = User(name=name.strip(), email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo("Administrador criado.")
