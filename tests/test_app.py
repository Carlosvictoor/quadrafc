"""Testes do site de ponta a ponta: cadastro, login, jogadores, pagamentos,
segurança (isolamento entre times e CSRF), CSV e exclusão de conta."""
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Notification, Payment, Player, Team, User
from app.services.months import MonthRef

from .conftest import NoCsrfConfig, add_player, signup


def test_paginas_publicas_e_protecao_de_login(client):
    assert client.get("/entrar").status_code == 200
    assert client.get("/criar-conta").status_code == 200
    assert client.get("/termos").status_code == 200
    # Sem login, o painel manda para a tela de entrar.
    resp = client.get("/")
    assert resp.status_code == 302 and "/entrar" in resp.headers["Location"]


def test_cadastro_cria_usuario_e_time(client, db_ctx):
    resp = signup(client)
    assert resp.status_code == 200
    assert "Olá, João!" in resp.get_data(as_text=True)
    with db_ctx():
        user = User.query.one()
        assert user.team.name == "Resenha FC"
        assert user.password_hash != "senha123"  # senha nunca em texto
        assert user.accepted_terms_at is not None


def test_cadastro_exige_aceite_e_email_unico(client):
    resp = client.post("/criar-conta", data={"name": "A", "team_name": "T", "email": "a@a.com",
                                             "password": "senha123"})
    assert "aceitar os Termos" in resp.get_data(as_text=True)
    signup(client, email="a@a.com")
    client.post("/sair")
    resp = signup(client, email="A@a.com")
    assert "Já existe uma conta" in resp.get_data(as_text=True)


def test_login_e_logout(client):
    signup(client)
    client.post("/sair")
    assert client.get("/").status_code == 302  # saiu de verdade
    resp = client.post("/entrar", data={"email": "joao@email.com", "password": "errada"})
    assert "E-mail ou senha incorretos" in resp.get_data(as_text=True)
    resp = client.post("/entrar", data={"email": "JOAO@email.com", "password": "senha123"},
                       follow_redirects=True)
    assert "Olá, João!" in resp.get_data(as_text=True)


def test_login_nao_redireciona_para_outro_site(client):
    signup(client)
    client.post("/sair")
    resp = client.post("/entrar?next=//site-malicioso.com",
                       data={"email": "joao@email.com", "password": "senha123"})
    assert "site-malicioso" not in resp.headers["Location"]


def test_fluxo_jogador_pagamento_desfazer(client, db_ctx):
    signup(client)
    add_player(client, "Lucas Silva")
    add_player(client, "Rafael Santos", status="paid")  # já entra como pago
    month = MonthRef.current()
    with db_ctx():
        lucas_id = Player.query.filter_by(name="Lucas Silva").one().id
        assert Payment.query.count() == 1

    # Registra o pagamento do Lucas.
    resp = client.post("/pagamentos/registrar", data={
        "player_id": lucas_id, "month": month.key, "amount": "20,00",
        "paid_on": "2026-10-18", "method": "dinheiro", "note": "pagou no jogo",
    }, follow_redirects=True)
    assert "Pagamento de Lucas Silva confirmado" in resp.get_data(as_text=True)
    with db_ctx():
        pay = Payment.query.filter_by(player_id=lucas_id).one()
        assert pay.amount_cents == 2000 and pay.method == "dinheiro" and pay.registered_by == "João Silva"

    # Registrar de novo no mesmo mês substitui (não duplica).
    client.post("/pagamentos/registrar", data={
        "player_id": lucas_id, "month": month.key, "amount": "25", "paid_on": "2026-10-19",
        "method": "pix"})
    with db_ctx():
        pays = Payment.query.filter_by(player_id=lucas_id).all()
        assert len(pays) == 1 and pays[0].amount_cents == 2500
        pay_id = pays[0].id

    # Painel mostra os totais: 20 (Rafael) + 25 (Lucas).
    assert "R$ 45,00" in client.get("/").get_data(as_text=True)

    # Desfazer volta para pendente.
    client.post(f"/pagamentos/{pay_id}/desfazer")
    with db_ctx():
        assert Payment.query.filter_by(player_id=lucas_id).count() == 0
        assert Notification.query.filter_by(type="payment_pending").count() == 1


def test_valor_invalido_e_rejeitado(client, db_ctx):
    signup(client)
    resp = add_player(client, "Zé", amount="abc")
    assert "Informe um valor válido" in resp.get_data(as_text=True)
    resp = add_player(client, "Zé", amount="0")
    assert "maior que zero" in resp.get_data(as_text=True)
    with db_ctx():
        assert Player.query.count() == 0


def test_remover_jogador_mantem_historico(client, db_ctx):
    signup(client)
    add_player(client, "Diego Alves", status="paid")
    with db_ctx():
        diego_id = Player.query.one().id
    client.post(f"/jogadores/{diego_id}/remover")
    with db_ctx():
        assert Player.query.count() == 0
        pay = Payment.query.one()
        assert pay.player_id is None and pay.player_name == "Diego Alves"
    assert "Diego Alves" in client.get("/historico").get_data(as_text=True)


def test_isolamento_entre_times(app, db_ctx):
    """O usuário B nunca acessa nada do time do usuário A."""
    a, b = app.test_client(), app.test_client()
    signup(a, email="a@x.com", team="Time A")
    add_player(a, "Jogador de A", status="paid")
    with db_ctx():
        player_id = Player.query.one().id
        payment_id = Payment.query.one().id

    signup(b, email="b@x.com", team="Time B")
    assert b.get(f"/jogadores/{player_id}/editar").status_code == 404
    assert b.post(f"/jogadores/{player_id}/editar", data={"name": "Hacker", "amount": "1"}).status_code == 404
    assert b.post(f"/jogadores/{player_id}/remover").status_code == 404
    assert b.post(f"/pagamentos/{payment_id}/desfazer").status_code == 404
    # Pagamento para jogador de outro time: não está nas opções -> recusado.
    b.post("/pagamentos/registrar", data={"player_id": player_id, "month": "2026-10",
                                          "amount": "20", "paid_on": "2026-10-18", "method": "pix"})
    assert "Jogador de A" not in b.get("/jogadores").get_data(as_text=True)
    assert "Jogador de A" not in b.get("/historico/csv").get_data(as_text=True)
    with db_ctx():
        # Nada de A foi alterado e nenhum pagamento novo foi criado.
        assert Payment.query.count() == 1
        assert db.session.get(Player, player_id).name == "Jogador de A"
    # E A continua acessando normalmente.
    assert a.get(f"/jogadores/{player_id}/editar").status_code == 200


def test_csv_do_historico(client):
    signup(client)
    add_player(client, "Lucas Silva", status="paid")
    add_player(client, "Bruno Costa")
    resp = client.get("/historico/csv")
    text = resp.get_data(as_text=True)
    assert resp.mimetype == "text/csv"
    assert "Data;Jogador;Valor;Forma;Status" in text
    assert "Lucas Silva;20,00;Pix;Pago" in text
    assert "Bruno Costa;20,00;—;Pendente" in text


def test_editar_quadra_e_compartilhar(client, db_ctx):
    signup(client)
    resp = client.post("/quadra/editar", data={
        "name": "Resenha FC", "description": "Time de amigos", "court_name": "Quadra do Zé",
        "court_address": "Rua A, 1", "court_cost": "240,00", "price_per_player": "20",
        "game_weekday": "5", "game_start": "19:00", "game_end": "21:00",
        "rules": "Regra 1\nRegra 2\n\n",
    }, follow_redirects=True)
    assert "Quadra do Zé" in resp.get_data(as_text=True)
    with db_ctx():
        team = Team.query.one()
        assert team.court_cost_cents == 24000 and team.game_weekday == 5
        assert team.rules_list == ["Regra 1", "Regra 2"]
    add_player(client, "Lucas Silva")
    html = client.get("/compartilhar").get_data(as_text=True)
    assert "wa.me/?text=" in html and "Lucas Silva" in html
    # Horário inválido é rejeitado.
    resp = client.post("/quadra/editar", data={"name": "X", "court_cost": "0", "price_per_player": "0",
                                               "game_start": "25:99"})
    assert "Use o formato HH:MM" in resp.get_data(as_text=True)


def test_todas_as_paginas_abrem(client):
    signup(client)
    add_player(client, "Lucas Silva", status="paid")
    for url in ["/", "/jogadores", "/jogadores?filtro=pendentes&ordem=nome&q=luc", "/jogadores/novo",
                "/pagamentos", "/pagamentos?mes=2020-01", "/pagamentos/registrar", "/historico",
                "/historico?situacao=pendente", "/quadra", "/quadra/editar", "/notificacoes",
                "/configuracoes", "/compartilhar", "/privacidade"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/nao-existe").status_code == 404


def test_notificacoes_marcadas_como_lidas(client, db_ctx):
    signup(client)
    add_player(client, "Lucas Silva")
    with db_ctx():
        assert Notification.query.filter_by(read=False).count() == 1
    client.get("/notificacoes")
    with db_ctx():
        assert Notification.query.filter_by(read=False).count() == 0


def test_alterar_senha_e_excluir_conta(client, db_ctx):
    signup(client)
    add_player(client, "Lucas Silva", status="paid")
    resp = client.post("/configuracoes", data={"senha-current": "errada", "senha-password": "nova123",
                                               "senha-confirm": "nova123", "senha-submit": "1"})
    assert "Senha atual incorreta" in resp.get_data(as_text=True)
    client.post("/configuracoes", data={"senha-current": "senha123", "senha-password": "nova123",
                                        "senha-confirm": "nova123", "senha-submit": "1"})
    with db_ctx():
        assert User.query.one().check_password("nova123")

    resp = client.post("/configuracoes", data={"excluir-password": "nova123", "excluir-submit": "1"},
                       follow_redirects=True)
    assert "foram excluídos" in resp.get_data(as_text=True)
    with db_ctx():
        # Tudo apagado em cascata.
        for model in (User, Team, Player, Payment, Notification):
            assert model.query.count() == 0, model.__name__


def test_redefinir_senha(client, db_ctx):
    from app.auth import make_reset_token
    signup(client)
    client.post("/sair")
    with db_ctx():
        token = make_reset_token(User.query.one())
    resp = client.post(f"/redefinir/{token}", data={"password": "outra123", "confirm": "outra123"},
                       follow_redirects=True)
    assert "Senha alterada" in resp.get_data(as_text=True)
    with db_ctx():
        assert User.query.one().check_password("outra123")
    # O mesmo link não funciona de novo (a senha mudou).
    resp = client.get(f"/redefinir/{token}", follow_redirects=True)
    assert "Link inválido" in resp.get_data(as_text=True)


def test_csrf_ativo_no_site_real():
    """Com a configuração normal, formulário sem token CSRF é recusado."""

    class CsrfOn(TestConfig):
        SQLALCHEMY_ENGINE_OPTIONS = NoCsrfConfig.SQLALCHEMY_ENGINE_OPTIONS

    app = create_app(CsrfOn)
    client = app.test_client()
    resp = client.post("/criar-conta", data={"name": "A", "team_name": "T", "email": "a@a.com",
                                             "password": "senha123", "accept_terms": "y"})
    assert resp.status_code == 400
    with app.app_context():
        assert User.query.count() == 0
        db.drop_all()


def test_cabecalhos_de_seguranca(client):
    resp = client.get("/entrar")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
