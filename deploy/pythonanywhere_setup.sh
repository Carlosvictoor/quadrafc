#!/bin/bash
# =====================================================================
# Instala o QuadraPro no PythonAnywhere.
# Rode no console "Bash" do PythonAnywhere:
#     bash ~/quadrapro/deploy/pythonanywhere_setup.sh
# Pode rodar de novo a qualquer momento (ex.: depois de atualizar o site):
# ele reinstala as dependências, mas NÃO apaga o banco nem troca a chave secreta.
# =====================================================================
set -e

# Vai para a pasta do projeto (a pasta acima desta).
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

# Escolhe a versão mais nova do Python disponível (o site precisa da 3.10 ou superior).
PY=""
for v in 3.13 3.12 3.11 3.10; do
  if command -v "python$v" >/dev/null 2>&1; then PY="python$v"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERRO: nenhum Python 3.10+ encontrado." >&2
  exit 1
fi
echo ">> Usando $PY"

# 1) Ambiente virtual com as bibliotecas do site.
if [ ! -d .venv ]; then
  echo ">> Criando ambiente virtual..."
  "$PY" -m venv .venv
fi
echo ">> Instalando dependências (pode levar 1 ou 2 minutos)..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

# 2) Arquivo .env com a chave secreta (criado só na primeira vez).
if [ ! -f .env ]; then
  echo ">> Gerando chave secreta (.env)..."
  KEY=$(.venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
  printf "FLASK_ENV=production\nSECRET_KEY=%s\n" "$KEY" > .env
  chmod 600 .env   # só o seu usuário consegue ler
fi

# 3) Cria as tabelas do banco (SQLite em instance/quadrapro.db).
.venv/bin/python -c "from app import create_app; create_app(); print('>> Banco de dados pronto')"

PY_VERSION=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo ""
echo "================= TUDO PRONTO ================="
echo "Na aba Web do PythonAnywhere, use:"
echo "  Python version : $PY_VERSION"
echo "  Virtualenv     : $PROJECT_DIR/.venv"
echo "  Static files   : URL /static/  ->  $PROJECT_DIR/app/static"
echo "  WSGI file      : cole o conteúdo de deploy/pythonanywhere_wsgi.py"
echo "Depois clique em Reload."
echo "==============================================="
