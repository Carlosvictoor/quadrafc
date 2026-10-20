"""Inicia o site em modo de desenvolvimento.

Uso:  python run.py   e abra http://127.0.0.1:5000 no navegador.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
