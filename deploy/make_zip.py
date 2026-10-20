"""Gera dist/quadrapro.zip com o projeto pronto para enviar à hospedagem.

Uso:  python deploy/make_zip.py

Inclui só o necessário. NÃO inclui: o ambiente virtual (.venv), o banco
local (instance/), o arquivo de segredos (.env), caches e o script de
dados de demonstração.
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist", "quadrapro.zip")

# Pastas e arquivos que entram no pacote.
INCLUDE = ["app", "deploy", "requirements.txt", "run.py", "README.md", ".env.example"]
# Nunca entram (mesmo que estejam dentro das pastas acima).
SKIP_DIRS = {"__pycache__", ".pytest_cache", "instance", ".venv"}
SKIP_FILES = {".env", "make_zip.py"}


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in INCLUDE:
            path = os.path.join(ROOT, item)
            if os.path.isfile(path):
                zf.write(path, item)
                count += 1
                continue
            for folder, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in files:
                    if name in SKIP_FILES or name.endswith(".pyc"):
                        continue
                    full = os.path.join(folder, name)
                    # Caminhos com "/" para funcionar no Linux da hospedagem.
                    zf.write(full, os.path.relpath(full, ROOT).replace(os.sep, "/"))
                    count += 1
    size_kb = os.path.getsize(OUT) // 1024
    print(f"Pacote criado: {OUT} ({count} arquivos, {size_kb} KB)")


if __name__ == "__main__":
    main()
