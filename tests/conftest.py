"""Preparação dos testes: cria um site com banco em memória para cada teste.

IMPORTANTE: não mantemos um "contexto do Flask" aberto durante o teste.
Assim cada requisição tem o próprio contexto, exatamente como num servidor
real (se o contexto fosse compartilhado, o login de um usuário "vazaria"
para a requisição de outro e o teste de isolamento ficaria errado).
Para consultar o banco no teste, use o fixture `db_ctx`:  with db_ctx(): ...
"""
import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from app.config import TestConfig
from app.extensions import db


class NoCsrfConfig(TestConfig):
    # Nos testes de fluxo desligamos o CSRF para enviar formulários direto.
    # Há um teste separado que confirma que o CSRF está ATIVO no site real.
    WTF_CSRF_ENABLED = False
    # Banco em memória compartilhado entre conexões (necessário sem contexto fixo).
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False},
                                 "poolclass": StaticPool}


@pytest.fixture
def app():
    app = create_app(NoCsrfConfig)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_ctx(app):
    """Abre um contexto só para consultar o banco dentro do teste."""
    return app.app_context


def signup(client, email="joao@email.com", name="João Silva", team="Resenha FC", password="senha123"):
    """Cria uma conta pelo formulário (o usuário fica logado)."""
    return client.post("/criar-conta", data={
        "name": name, "team_name": team, "email": email,
        "password": password, "accept_terms": "y",
    }, follow_redirects=True)


def add_player(client, name, amount="20,00", status="pending"):
    return client.post("/jogadores/novo", data={
        "name": name, "amount": amount, "initial_status": status,
    }, follow_redirects=True)
