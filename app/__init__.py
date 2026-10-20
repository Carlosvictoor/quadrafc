"""Criação do site Flask (padrão "application factory").

create_app() monta o site: carrega a configuração, conecta o banco,
o login e a proteção CSRF, registra as páginas e os filtros de formatação.
"""
import os

from dotenv import load_dotenv

# Lê o arquivo .env (na pasta do projeto) ANTES de importar a configuração,
# porque o config.py lê as variáveis de ambiente assim que é importado.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from flask import Flask, render_template  # noqa: E402
from flask_login import current_user  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from .config import DevConfig, ProdConfig  # noqa: E402
from .extensions import csrf, db, login_manager
from .services.money import format_cents
from .services.months import WEEKDAY_NAMES, MonthRef, long_date, short_date


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _record):
    """Liga a checagem de chaves estrangeiras no SQLite (vem desligada por padrão)."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(config_class=None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    if config_class is None:
        config_class = ProdConfig if os.environ.get("FLASK_ENV") == "production" else DevConfig
    app.config.from_object(config_class)

    # Em produção o site fica atrás de um "proxy" da hospedagem (que cuida do HTTPS).
    # O ProxyFix faz o Flask saber que o acesso original foi em https e qual o domínio,
    # para gerar links corretos (ex.: o link de redefinir senha).
    if config_class is ProdConfig:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Banco: DATABASE_URL (PostgreSQL) ou SQLite local na pasta instance/.
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if uri.startswith("postgres://"):  # alguns provedores usam o prefixo antigo
        uri = uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif uri.startswith("postgresql://"):
        uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if not uri:
        os.makedirs(app.instance_path, exist_ok=True)
        uri = "sqlite:///" + os.path.join(app.instance_path, "quadrapro.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = uri

    # Em produção, recusa iniciar com a chave secreta padrão (inseguro).
    if not app.debug and not app.testing and app.config["SECRET_KEY"].startswith("dev-"):
        raise RuntimeError("Defina SECRET_KEY no ambiente antes de rodar em produção.")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .auth import bp as auth_bp
    from .main import bp as main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    _register_template_helpers(app)
    _register_error_pages(app)
    _register_security_headers(app)

    # Cria as tabelas na primeira execução.
    with app.app_context():
        db.create_all()
    return app


@login_manager.user_loader
def _load_user(user_id: str):
    """Recarrega o usuário logado a partir do id guardado na sessão."""
    from .models import User
    return db.session.get(User, int(user_id))


def _register_template_helpers(app: Flask) -> None:
    """Filtros e variáveis disponíveis em todos os templates HTML."""
    app.jinja_env.filters["brl"] = format_cents
    app.jinja_env.filters["data"] = lambda d: d.strftime("%d/%m/%Y") if d else "—"
    app.jinja_env.filters["dia_mes"] = lambda d: d.strftime("%d/%m") if d else "—"
    app.jinja_env.filters["data_hora"] = lambda d: d.strftime("%d/%m · %H:%M") if d else ""
    app.jinja_env.filters["data_longa"] = long_date
    app.jinja_env.filters["data_curta"] = short_date

    def initials(name: str) -> str:
        parts = [p for p in (name or "").split() if p]
        if not parts:
            return "?"
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    app.jinja_env.filters["iniciais"] = initials

    @app.context_processor
    def inject_globals():
        from .forms import EmptyForm
        from .models import Notification
        unread = 0
        if current_user.is_authenticated and current_user.team:
            unread = Notification.query.filter_by(team_id=current_user.team.id, read=False).count()
        # logout_form: o botão "Sair" é um formulário POST com token CSRF.
        return {"unread_count": unread, "current_month": MonthRef.current(),
                "logout_form": EmptyForm(), "weekday_names": WEEKDAY_NAMES}


def _register_error_pages(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/error.html", code=404,
                               title="Página não encontrada",
                               message="O endereço não existe ou você não tem acesso a ele."), 404

    @app.errorhandler(400)
    def bad_request(_e):
        return render_template("errors/error.html", code=400,
                               title="Não foi possível concluir",
                               message="A página expirou. Volte, recarregue e tente novamente."), 400

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template("errors/error.html", code=500,
                               title="Algo deu errado",
                               message="Tivemos um problema no servidor. Tente novamente."), 500


def _register_security_headers(app: Flask) -> None:
    """Cabeçalhos HTTP de segurança enviados em toda resposta."""

    @app.after_request
    def add_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp
