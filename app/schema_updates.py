"""Idempotent upgrade for installations created before catalog variants.

Run from the single startup process, before serving requests. PostgreSQL uses a
transaction and an advisory lock; SQLite uses Alembic's batch table rebuild.
"""
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from .extensions import db
from .product_options import default_colors


def upgrade_product_options():
    with db.engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(710202611)"))
        op = Operations(MigrationContext.configure(connection))
        columns = {c["name"] for c in sa.inspect(connection).get_columns("products")}
        additions = [
            sa.Column("laser_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sublimation_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("colors", sa.JSON(), nullable=True),
        ]
        for column in additions:
            if column.name not in columns:
                op.add_column("products", column)
        products = sa.table("products", sa.column("colors", sa.JSON()))
        connection.execute(products.update().where(products.c.colors.is_(None)).values(colors=default_colors()))
        if sa.inspect(connection).get_columns("products"):
            color_column = next(c for c in sa.inspect(connection).get_columns("products") if c["name"] == "colors")
            if color_column["nullable"]:
                with op.batch_alter_table("products") as batch:
                    batch.alter_column("colors", existing_type=sa.JSON(), nullable=False)
        columns = {c["name"] for c in sa.inspect(connection).get_columns("cart_items")}
        additions = [
            sa.Column("variant_key", sa.String(64), nullable=False, server_default=""),
            sa.Column("color_name_snapshot", sa.String(60)),
            sa.Column("color_id_snapshot", sa.String(64)),
            sa.Column("color_hex_snapshot", sa.String(7)),
            sa.Column("method_snapshot", sa.String(30)),
        ]
        for column in additions:
            if column.name not in columns:
                op.add_column("cart_items", column)
        constraints = {c["name"] for c in sa.inspect(connection).get_unique_constraints("cart_items")}
        if "uq_cart_product" in constraints or "uq_cart_product_variant" not in constraints:
            with op.batch_alter_table("cart_items") as batch:
                if "uq_cart_product" in constraints:
                    batch.drop_constraint("uq_cart_product", type_="unique")
                if "uq_cart_product_variant" not in constraints:
                    batch.create_unique_constraint("uq_cart_product_variant", ["cart_id", "product_id", "variant_key"])
