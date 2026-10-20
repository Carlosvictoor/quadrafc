# =====================================================================
# Arquivo WSGI do QuadraPro para o PythonAnywhere.
# Copie TODO este conteúdo para o arquivo WSGI do seu site
# (aba Web -> "WSGI configuration file"), substituindo o que estiver lá.
# Não precisa trocar nada: o caminho é descoberto automaticamente.
# =====================================================================
import os
import sys

# Pasta do projeto: /home/SEU_USUARIO/quadrapro
PROJECT_DIR = os.path.expanduser("~/quadrapro")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# O app/__init__.py carrega o arquivo .env (FLASK_ENV e SECRET_KEY) sozinho.
from app import create_app  # noqa: E402

# O PythonAnywhere procura uma variável chamada "application".
application = create_app()
