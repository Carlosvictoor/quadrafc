"""Configurações do site.

Em desenvolvimento usa SQLite (um arquivo em instance/quadrapro.db).
Em produção lê tudo das variáveis de ambiente (arquivo .env ou painel da hospedagem).
"""
import os
from datetime import timedelta


class Config:
    # Chave usada para assinar a sessão e os links de redefinição de senha.
    # Em produção DEVE vir do ambiente (nunca deixe a chave de desenvolvimento).
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-chave-insegura-troque-em-producao")

    # Banco de dados. Se DATABASE_URL não existir, usa SQLite local.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies da sessão: inacessíveis ao JavaScript e protegidos contra CSRF entre sites.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    # "Lembrar de mim" mantém o login por 30 dias.
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Formulários: o token CSRF vale por 2 horas.
    WTF_CSRF_TIME_LIMIT = 7200

    # E-mail (opcional) para "Esqueci minha senha".
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False
    # Em produção o site roda em HTTPS: cookies só trafegam criptografados.
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "chave-de-teste"
    SQLALCHEMY_DATABASE_URI = "sqlite://"  # banco só na memória
    SERVER_NAME = "localhost"
