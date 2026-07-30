"""Inicialização segura para Railway.

Espera o PostgreSQL ficar disponível e executa o bootstrap antes de iniciar o
Gunicorn. As tentativas têm tempo limitado, evitando um processo silencioso ou
preso indefinidamente.
"""
from __future__ import annotations

import os
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.cli import bootstrap_database
from app.extensions import db


def main() -> None:
    app = create_app()
    attempts = max(1, int(os.getenv("DB_STARTUP_ATTEMPTS", "30")))
    delay = max(1, int(os.getenv("DB_STARTUP_DELAY", "2")))

    with app.app_context():
        for attempt in range(1, attempts + 1):
            try:
                db.session.execute(text("SELECT 1"))
                db.session.rollback()
                print(f"[startup] PostgreSQL disponível (tentativa {attempt}/{attempts}).", flush=True)
                bootstrap_database(app)
                print("[startup] Banco, configurações e administrador verificados.", flush=True)
                return
            except SQLAlchemyError as exc:
                db.session.rollback()
                print(
                    f"[startup] Banco indisponível (tentativa {attempt}/{attempts}): "
                    f"{exc.__class__.__name__}",
                    flush=True,
                )
                if attempt < attempts:
                    time.sleep(delay)

    print("[startup] Não foi possível conectar ao PostgreSQL dentro do limite.", file=sys.stderr, flush=True)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
