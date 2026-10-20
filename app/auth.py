"""Login, cadastro, saída e recuperação de senha."""
from datetime import datetime
from urllib.parse import urlsplit

from flask import (Blueprint, current_app, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db
from .forms import (EmptyForm, ForgotPasswordForm, LoginForm, ResetPasswordForm,
                    SignupForm)
from .models import Team, User
from .services.mailer import MailNotConfigured, send_email

bp = Blueprint("auth", __name__)

# Tempo de validade do link de redefinição de senha (1 hora).
RESET_MAX_AGE = 3600


def _safe_next(target: str | None) -> str | None:
    """Só aceita redirecionar para páginas do próprio site (evita "open redirect")."""
    if target and target.startswith("/") and not target.startswith("//") and not urlsplit(target).netloc:
        return target
    return None


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        # Mesma mensagem para e-mail ou senha errados (não revela quem tem conta).
        if user is None or not user.check_password(form.password.data):
            flash("E-mail ou senha incorretos.", "error")
        else:
            login_user(user, remember=form.remember.data)
            return redirect(_safe_next(request.args.get("next")) or url_for("main.dashboard"))
    return render_template("auth/login.html", form=form)


@bp.route("/criar-conta", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append("Já existe uma conta com este e-mail.")
        else:
            # Cria o usuário e o time juntos (uma única gravação).
            user = User(name=form.name.data.strip(), email=email,
                        accepted_terms_at=datetime.now())
            user.set_password(form.password.data)
            user.team = Team(name=form.team_name.data.strip())
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f"Bem-vindo ao QuadraPro, {user.first_name}! Comece adicionando seus jogadores.",
                  "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/signup.html", form=form)


@bp.post("/sair")
@login_required
def logout():
    # Só por POST (com token CSRF), para um link malicioso não deslogar ninguém.
    if EmptyForm().validate_on_submit():
        logout_user()
        flash("Você saiu da sua conta.", "info")
    return redirect(url_for("auth.login"))


# ---------------------- Recuperação de senha ----------------------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="redefinir-senha")


def make_reset_token(user: User) -> str:
    # Inclui parte do hash atual: o link deixa de valer depois que a senha muda.
    return _serializer().dumps({"uid": user.id, "h": user.password_hash[-12:]})


def _user_from_token(token: str) -> User | None:
    try:
        data = _serializer().loads(token, max_age=RESET_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
    user = db.session.get(User, data.get("uid"))
    if user is None or user.password_hash[-12:] != data.get("h"):
        return None
    return user


@bp.route("/esqueci-senha", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user:
            link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
            try:
                send_email(
                    user.email,
                    "QuadraPro - Redefinir senha",
                    f"Olá, {user.first_name}!\n\nPara criar uma nova senha, acesse o link abaixo "
                    f"(válido por 1 hora):\n\n{link}\n\nSe você não pediu, ignore este e-mail.",
                )
            except MailNotConfigured:
                flash("O envio de e-mail ainda não foi configurado neste site.", "error")
                return render_template("auth/forgot.html", form=form)
        # Mesma resposta exista ou não a conta (não revela quem é cadastrado).
        return render_template("auth/forgot.html", form=form, sent=form.email.data.strip())
    return render_template("auth/forgot.html", form=form)


@bp.route("/redefinir/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = _user_from_token(token)
    if user is None:
        flash("Link inválido ou expirado. Peça um novo.", "error")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Senha alterada! Entre com a nova senha.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", form=form)
