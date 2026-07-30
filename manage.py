import os
import sys

from app import create_app
from app.cli import bootstrap_database

app = create_app()


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "bootstrap":
        with app.app_context():
            bootstrap_database(app)
        print("Banco, configurações e administrador verificados com sucesso.")
        return
    if command == "serve":
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
        return
    raise SystemExit(f"Comando desconhecido: {command}")


if __name__ == "__main__":
    main()
