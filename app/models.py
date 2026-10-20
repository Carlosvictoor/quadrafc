"""Tabelas do banco de dados (SQLAlchemy).

Cada usuário administra UM time. Todos os dados (jogadores, pagamentos,
avisos) pertencem a um time, e as consultas sempre filtram pelo time do
usuário logado, garantindo que ninguém veja os dados de outro time.
"""
from datetime import date, datetime

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

# Formas de pagamento aceitas: chave salva no banco -> nome exibido.
PAYMENT_METHODS = {
    "pix": "Pix",
    "dinheiro": "Dinheiro",
    "transferencia": "Transferência",
    "outro": "Outro",
}


def utcnow() -> datetime:
    return datetime.now()


class User(UserMixin, db.Model):
    """Administrador do time (quem faz login no site)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    # Guardamos só o "hash" da senha (embaralhamento sem volta), nunca a senha.
    password_hash = db.Column(db.String(255), nullable=False)
    accepted_terms_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Time do usuário. Apagar o usuário apaga o time e tudo dentro dele.
    team = db.relationship("Team", back_populates="owner", uselist=False,
                           cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name else ""


class Team(db.Model):
    """Time e dados da quadra."""

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    name = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(120), default="Time de amigos, grandes jogos!")
    court_name = db.Column(db.String(80), default="")
    court_address = db.Column(db.String(160), default="")
    # Valores em centavos.
    court_cost_cents = db.Column(db.Integer, default=0, nullable=False)
    price_per_player_cents = db.Column(db.Integer, default=2000, nullable=False)
    # Jogo semanal: dia da semana (0 = segunda ... 6 = domingo) e horários "HH:MM".
    game_weekday = db.Column(db.Integer)
    game_start = db.Column(db.String(5), default="")
    game_end = db.Column(db.String(5), default="")
    # Regras do time, uma por linha.
    rules = db.Column(db.Text, default="Pagamento até o dia do jogo\nFaltas devem ser avisadas\nRespeito sempre!")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="team")
    players = db.relationship("Player", back_populates="team", cascade="all, delete-orphan",
                              order_by="Player.name")
    payments = db.relationship("Payment", back_populates="team", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="team",
                                    cascade="all, delete-orphan")

    @property
    def rules_list(self) -> list[str]:
        return [r.strip() for r in (self.rules or "").splitlines() if r.strip()]

    @property
    def active_players(self) -> list["Player"]:
        return [p for p in self.players if p.active]


class Player(db.Model):
    """Jogador do time."""

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    nickname = db.Column(db.String(40), default="")
    phone = db.Column(db.String(30), default="")
    # Quanto o jogador paga por mês, em centavos.
    amount_cents = db.Column(db.Integer, nullable=False)
    # Jogadores inativos não entram no valor pendente.
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    team = db.relationship("Team", back_populates="players")
    payments = db.relationship("Payment", back_populates="player", passive_deletes=True)

    @property
    def display_name(self) -> str:
        """Nome com apelido entre aspas, se houver. Ex.: Carlos "Carlão" Silva."""
        return f'{self.name} ({self.nickname})' if self.nickname else self.name


class Payment(db.Model):
    """Pagamento de um jogador em um mês. No máximo um por jogador por mês."""

    __table_args__ = (UniqueConstraint("team_id", "player_id", "month_key",
                                       name="uq_pagamento_por_mes"),)

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False, index=True)
    # Se o jogador for removido, o pagamento continua no histórico (player_id vira nulo).
    player_id = db.Column(db.Integer, db.ForeignKey("player.id", ondelete="SET NULL"))
    # Nome guardado junto, para o histórico continuar legível.
    player_name = db.Column(db.String(60), nullable=False)
    month_key = db.Column(db.String(7), nullable=False, index=True)  # "AAAA-MM"
    amount_cents = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(20), nullable=False, default="pix")
    paid_on = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(200), default="")
    # Quem registrou o pagamento (nome do administrador).
    registered_by = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    team = db.relationship("Team", back_populates="payments")
    player = db.relationship("Player", back_populates="payments")

    @property
    def method_label(self) -> str:
        return PAYMENT_METHODS.get(self.method, "Outro")


class Notification(db.Model):
    """Aviso exibido na tela de notificações e no sininho."""

    TYPES = ("payment_confirmed", "payment_pending", "new_player", "reminder")

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False, index=True)
    type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    body = db.Column(db.String(200), default="")
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    team = db.relationship("Team", back_populates="notifications")


def notify(team: Team, type_: str, title: str, body: str) -> None:
    """Cria um aviso para o time (gravado junto com a ação que o gerou)."""
    db.session.add(Notification(team=team, type=type_, title=title, body=body))
