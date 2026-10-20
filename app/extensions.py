"""Extensões do Flask criadas uma única vez e ligadas ao app em create_app()."""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# Banco de dados (SQLAlchemy).
db = SQLAlchemy()

# Controle de login: quem não está logado é mandado para a tela de entrar.
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Entre na sua conta para continuar."
login_manager.login_message_category = "info"

# Proteção CSRF: todo formulário precisa de um token secreto.
csrf = CSRFProtect()
