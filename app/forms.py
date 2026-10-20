"""Formulários do site (Flask-WTF).

Cada formulário valida os dados NO SERVIDOR (mesmo que o navegador seja
burlado) e inclui o token CSRF automaticamente.
"""
from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateField, EmailField, PasswordField, RadioField,
                     SelectField, StringField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional, Regexp,
                                ValidationError)

from .models import PAYMENT_METHODS
from .services.money import parse_cents
from .services.months import WEEKDAY_NAMES

# Mensagens padrão em português.
REQUIRED = "Campo obrigatório"


class MoneyField(StringField):
    """Campo de dinheiro: aceita "20", "20,00", "R$ 1.234,56"...
    Depois de validado, o valor em centavos fica em `field.cents`."""

    cents: int | None = None

    def __init__(self, label=None, allow_zero=False, **kwargs):
        super().__init__(label, **kwargs)
        self.allow_zero = allow_zero

    def pre_validate(self, form):
        self.cents = parse_cents(self.data)
        if self.cents is None:
            raise ValidationError("Informe um valor válido. Ex.: 20,00")
        if not self.allow_zero and self.cents == 0:
            raise ValidationError("O valor precisa ser maior que zero")
        if self.cents > 100_000_000:
            raise ValidationError("Valor muito alto")


TIME_REGEX = Regexp(r"^([01]\d|2[0-3]):[0-5]\d$", message="Use o formato HH:MM. Ex.: 19:00")


# ---------------------------- Autenticação ----------------------------

class LoginForm(FlaskForm):
    email = EmailField("E-mail", validators=[DataRequired(REQUIRED), Email("E-mail inválido")])
    password = PasswordField("Senha", validators=[DataRequired(REQUIRED)])
    remember = BooleanField("Lembrar de mim")


class SignupForm(FlaskForm):
    name = StringField("Nome completo", validators=[DataRequired(REQUIRED), Length(max=80)])
    team_name = StringField("Nome do time", validators=[DataRequired(REQUIRED), Length(max=60)])
    email = EmailField("E-mail", validators=[DataRequired(REQUIRED), Email("E-mail inválido"),
                                             Length(max=200)])
    password = PasswordField("Senha", validators=[
        DataRequired(REQUIRED), Length(min=6, max=128, message="Mínimo de 6 caracteres")])
    accept_terms = BooleanField("Aceito os termos", validators=[
        DataRequired("Você precisa aceitar os Termos de Uso e a Política de Privacidade")])


class ForgotPasswordForm(FlaskForm):
    email = EmailField("E-mail", validators=[DataRequired(REQUIRED), Email("E-mail inválido")])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Nova senha", validators=[
        DataRequired(REQUIRED), Length(min=6, max=128, message="Mínimo de 6 caracteres")])
    confirm = PasswordField("Confirme a nova senha", validators=[
        EqualTo("password", message="As senhas não conferem")])


# ---------------------------- Jogadores ----------------------------

class PlayerForm(FlaskForm):
    name = StringField("Nome completo", validators=[DataRequired(REQUIRED), Length(max=60)])
    nickname = StringField("Apelido (opcional)", validators=[Optional(), Length(max=40)])
    phone = StringField("Telefone (opcional)", validators=[Optional(), Length(max=30)])
    amount = MoneyField("Valor padrão a pagar")
    initial_status = RadioField("Situação inicial", choices=[("paid", "Pago"), ("pending", "Pendente")],
                                default="pending")
    active = BooleanField("Jogador ativo", default=True)


# ---------------------------- Pagamentos ----------------------------

class PaymentForm(FlaskForm):
    player_id = SelectField("Jogador", coerce=int, validators=[DataRequired("Escolha o jogador")])
    month = StringField("Mês de referência", validators=[
        DataRequired(REQUIRED), Regexp(r"^\d{4}-\d{2}$", message="Mês inválido")])
    amount = MoneyField("Valor pago")
    paid_on = DateField("Data do pagamento", validators=[DataRequired("Informe a data")])
    method = SelectField("Forma de pagamento", choices=list(PAYMENT_METHODS.items()))
    note = StringField("Observação (opcional)", validators=[Optional(), Length(max=200)])


# ---------------------------- Time e quadra ----------------------------

class TeamForm(FlaskForm):
    name = StringField("Nome do time", validators=[DataRequired(REQUIRED), Length(max=60)])
    description = StringField("Frase do time", validators=[Optional(), Length(max=120)])
    court_name = StringField("Nome da quadra", validators=[Optional(), Length(max=80)])
    court_address = StringField("Endereço", validators=[Optional(), Length(max=160)])
    court_cost = MoneyField("Valor total da quadra (por mês)", allow_zero=True)
    price_per_player = MoneyField("Valor padrão por jogador", allow_zero=True)
    game_weekday = SelectField("Dia da semana do jogo",
                               choices=[("", "Sem jogo fixo")] + [(str(i), n) for i, n in enumerate(WEEKDAY_NAMES)])
    game_start = StringField("Início", validators=[Optional(), TIME_REGEX])
    game_end = StringField("Fim", validators=[Optional(), TIME_REGEX])
    rules = TextAreaField("Regras do time (uma por linha)", validators=[Optional(), Length(max=2000)])


# ---------------------------- Conta ----------------------------

class AccountForm(FlaskForm):
    name = StringField("Seu nome", validators=[DataRequired(REQUIRED), Length(max=80)])
    email = EmailField("E-mail", validators=[DataRequired(REQUIRED), Email("E-mail inválido"),
                                             Length(max=200)])


class ChangePasswordForm(FlaskForm):
    current = PasswordField("Senha atual", validators=[DataRequired(REQUIRED)])
    password = PasswordField("Nova senha", validators=[
        DataRequired(REQUIRED), Length(min=6, max=128, message="Mínimo de 6 caracteres")])
    confirm = PasswordField("Confirme a nova senha", validators=[
        EqualTo("password", message="As senhas não conferem")])


class DeleteAccountForm(FlaskForm):
    password = PasswordField("Digite sua senha para confirmar", validators=[DataRequired(REQUIRED)])


class EmptyForm(FlaskForm):
    """Formulário vazio: só carrega o token CSRF (botões de ação via POST)."""
