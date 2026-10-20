"""Telas internas do site (exigem login): painel, jogadores, pagamentos,
histórico, quadra, notificações, configurações e compartilhar resumo."""
import csv
import io
from datetime import date, datetime, timedelta
from urllib.parse import quote

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required, logout_user

from .extensions import db
from .forms import (AccountForm, ChangePasswordForm, DeleteAccountForm, EmptyForm,
                    PaymentForm, PlayerForm, TeamForm)
from .models import Notification, Payment, Player, Team, User, notify
from .services.money import cents_to_input, format_cents
from .services.months import MonthRef, long_date, next_game
from .services.summary import compute_summary

bp = Blueprint("main", __name__)


# ------------------------------ Auxiliares ------------------------------

def get_team() -> Team:
    """Time do usuário logado. Todas as consultas partem daqui."""
    team = current_user.team
    if team is None:  # não deveria acontecer: o cadastro sempre cria o time
        abort(404)
    return team


def get_player(team: Team, player_id: int) -> Player:
    """Busca um jogador SÓ dentro do time do usuário (senão, 404)."""
    return Player.query.filter_by(id=player_id, team_id=team.id).first_or_404()


def month_payments(team: Team, month: MonthRef) -> list[Payment]:
    return Payment.query.filter_by(team_id=team.id, month_key=month.key).all()


def month_summary(team: Team, month: MonthRef):
    return compute_summary(team.players, month_payments(team, month))


def selected_month() -> MonthRef:
    """Mês escolhido pelo parâmetro ?mes=AAAA-MM (padrão: mês atual)."""
    return MonthRef.parse(request.args.get("mes"))


def can_go_next(month: MonthRef) -> bool:
    """Permite navegar até 1 mês depois do atual (para adiantar cobranças)."""
    return month.next <= MonthRef.current().next


# ------------------------------ Painel ------------------------------

@bp.route("/")
@login_required
def dashboard():
    team = get_team()
    month = MonthRef.current()
    summary = month_summary(team, month)
    game = next_game(team.game_weekday, team.game_start)
    return render_template("dashboard.html", team=team, month=month, summary=summary,
                           game=game, nav="inicio")


# ------------------------------ Jogadores ------------------------------

@bp.route("/jogadores")
@login_required
def players():
    team = get_team()
    month = MonthRef.current()
    summary = month_summary(team, month)
    status = request.args.get("filtro", "todos")
    order = request.args.get("ordem", "pendentes")
    query = request.args.get("q", "").strip().lower()

    rows = list(team.players)
    if query:
        rows = [p for p in rows if query in p.name.lower() or query in (p.nickname or "").lower()]
    if status == "pagos":
        rows = [p for p in rows if summary.is_paid(p.id)]
    elif status == "pendentes":
        rows = [p for p in rows if p.active and not summary.is_paid(p.id)]
    if order == "pendentes":
        # Pendentes primeiro, depois pagos, inativos por último; dentro de cada grupo, por nome.
        rows.sort(key=lambda p: (not p.active, summary.is_paid(p.id), p.name.lower()))
    else:
        rows.sort(key=lambda p: p.name.lower())

    return render_template("players.html", team=team, rows=rows, summary=summary, month=month,
                           status=status, order=order, query=query, nav="jogadores")


@bp.route("/jogadores/novo", methods=["GET", "POST"])
@login_required
def player_new():
    team = get_team()
    form = PlayerForm()
    if request.method == "GET":
        form.amount.data = cents_to_input(team.price_per_player_cents or 2000)
    if form.validate_on_submit():
        player = Player(team=team, name=form.name.data.strip(), nickname=(form.nickname.data or "").strip(),
                        phone=(form.phone.data or "").strip(), amount_cents=form.amount.cents)
        db.session.add(player)
        db.session.flush()  # gera o id do jogador antes de criar o pagamento
        notify(team, "new_player", "Novo jogador", f"{player.name} foi adicionado ao time.")
        if form.initial_status.data == "paid":
            month = MonthRef.current()
            db.session.add(Payment(team=team, player=player, player_name=player.name,
                                   month_key=month.key, amount_cents=player.amount_cents,
                                   method="pix", paid_on=date.today(),
                                   registered_by=current_user.name))
            notify(team, "payment_confirmed", "Pagamento registrado",
                   f"{player.name} pagou {format_cents(player.amount_cents)}.")
        db.session.commit()
        flash(f"{player.name} adicionado ao time!", "success")
        return redirect(url_for("main.players"))
    return render_template("player_form.html", form=form, player=None, nav="jogadores")


@bp.route("/jogadores/<int:player_id>/editar", methods=["GET", "POST"])
@login_required
def player_edit(player_id):
    team = get_team()
    player = get_player(team, player_id)
    form = PlayerForm(obj=player)
    if request.method == "GET":
        form.amount.data = cents_to_input(player.amount_cents)
    if form.validate_on_submit():
        player.name = form.name.data.strip()
        player.nickname = (form.nickname.data or "").strip()
        player.phone = (form.phone.data or "").strip()
        player.amount_cents = form.amount.cents
        player.active = form.active.data
        db.session.commit()
        flash("Jogador atualizado!", "success")
        return redirect(url_for("main.players"))
    return render_template("player_form.html", form=form, player=player, delete_form=EmptyForm(),
                           nav="jogadores")


@bp.post("/jogadores/<int:player_id>/remover")
@login_required
def player_delete(player_id):
    team = get_team()
    player = get_player(team, player_id)
    if EmptyForm().validate_on_submit():
        # Os pagamentos já feitos continuam no histórico, sem ligação com o jogador.
        for payment in player.payments:
            payment.player_id = None
        db.session.delete(player)
        db.session.commit()
        flash(f"{player.name} foi removido. O histórico de pagamentos foi mantido.", "success")
    return redirect(url_for("main.players"))


# ------------------------------ Pagamentos ------------------------------

@bp.route("/pagamentos")
@login_required
def payments():
    team = get_team()
    month = selected_month()
    summary = month_summary(team, month)
    paid_rows = [(p, summary.payments_by_player[p.id]) for p in team.active_players
                 if summary.is_paid(p.id)]
    return render_template("payments.html", team=team, month=month, summary=summary,
                           paid_rows=paid_rows, can_next=can_go_next(month),
                           action_form=EmptyForm(), nav="pagamentos")


@bp.route("/pagamentos/registrar", methods=["GET", "POST"])
@login_required
def payment_new():
    team = get_team()
    active = team.active_players
    if not active:
        flash("Cadastre um jogador antes de registrar pagamentos.", "info")
        return redirect(url_for("main.player_new"))

    form = PaymentForm()
    month = MonthRef.parse(request.values.get("mes") or request.form.get("month"))
    summary = month_summary(team, month)
    # Lista de jogadores: pendentes primeiro.
    ordered = sorted(active, key=lambda p: (summary.is_paid(p.id), p.name.lower()))
    form.player_id.choices = [
        (p.id, f"{p.name} — {'Pago' if summary.is_paid(p.id) else 'Pendente'}") for p in ordered]

    if request.method == "GET":
        chosen = request.args.get("jogador", type=int)
        player = next((p for p in active if p.id == chosen), ordered[0])
        form.player_id.data = player.id
        form.month.data = month.key
        form.amount.data = cents_to_input(player.amount_cents)
        form.paid_on.data = date.today()

    if form.validate_on_submit():
        player = get_player(team, form.player_id.data)
        month = MonthRef.parse(form.month.data)
        payment = Payment.query.filter_by(team_id=team.id, player_id=player.id,
                                          month_key=month.key).first()
        if payment is None:
            payment = Payment(team=team, player=player, month_key=month.key)
            db.session.add(payment)
        # Se já existia pagamento no mês, ele é substituído pelos novos dados.
        payment.player_name = player.name
        payment.amount_cents = form.amount.cents
        payment.method = form.method.data
        payment.paid_on = form.paid_on.data
        payment.note = (form.note.data or "").strip()
        payment.registered_by = current_user.name
        notify(team, "payment_confirmed", "Pagamento registrado",
               f"{player.name} pagou {format_cents(payment.amount_cents)} via {payment.method_label}.")
        db.session.commit()
        flash(f"Pagamento de {player.name} confirmado!", "success")
        return redirect(url_for("main.payments", mes=month.key))

    players_json = {p.id: {"name": p.name, "amount": cents_to_input(p.amount_cents),
                           "paid": summary.is_paid(p.id)} for p in active}
    return render_template("payment_form.html", form=form, month=month, players_json=players_json,
                           nav="pagamentos")


@bp.post("/pagamentos/<int:payment_id>/desfazer")
@login_required
def payment_undo(payment_id):
    team = get_team()
    payment = Payment.query.filter_by(id=payment_id, team_id=team.id).first_or_404()
    month_key = payment.month_key
    if EmptyForm().validate_on_submit():
        notify(team, "payment_pending", "Pagamento pendente",
               f"{payment.player_name} voltou para a lista de pendentes.")
        db.session.delete(payment)
        db.session.commit()
        flash(f"{payment.player_name} voltou para pendente.", "success")
    # Volta para a página de origem, mas só se for um endereço do próprio site.
    back = request.form.get("voltar", "")
    if back.startswith("/") and not back.startswith("//"):
        return redirect(back)
    return redirect(url_for("main.payments", mes=month_key))


# ------------------------------ Histórico ------------------------------

def history_rows(team: Team, month: MonthRef, player_id: int | None, status: str):
    """Linhas do histórico: pagamentos do mês + jogadores ativos pendentes."""
    payments = month_payments(team, month)
    summary = compute_summary(team.players, payments)
    rows = [{"date": p.paid_on, "player": p.player_name, "player_id": p.player_id,
             "amount": p.amount_cents, "method": p.method_label, "method_key": p.method, "paid": True,
             "by": p.registered_by, "note": p.note} for p in payments]
    rows += [{"date": None, "player": p.name, "player_id": p.id, "amount": p.amount_cents,
              "method": "—", "method_key": "", "paid": False, "by": "", "note": ""} for p in summary.pending_players]
    if player_id:
        rows = [r for r in rows if r["player_id"] == player_id]
    if status == "pago":
        rows = [r for r in rows if r["paid"]]
    elif status == "pendente":
        rows = [r for r in rows if not r["paid"]]
    # Pagos do mais recente para o mais antigo; pendentes no fim.
    rows.sort(key=lambda r: (not r["paid"], -(r["date"].toordinal() if r["date"] else 0), r["player"]))
    return rows, summary


@bp.route("/historico")
@login_required
def history():
    team = get_team()
    month = selected_month()
    player_id = request.args.get("jogador", type=int)
    status = request.args.get("situacao", "todos")
    rows, summary = history_rows(team, month, player_id, status)
    return render_template("history.html", team=team, month=month, rows=rows, summary=summary,
                           player_id=player_id, status=status, can_next=can_go_next(month),
                           nav="historico")


@bp.route("/historico/csv")
@login_required
def history_csv():
    """Baixa o histórico do mês em CSV (abre no Excel / Google Planilhas)."""
    team = get_team()
    month = selected_month()
    rows, _ = history_rows(team, month, request.args.get("jogador", type=int),
                           request.args.get("situacao", "todos"))
    out = io.StringIO()
    # Ponto e vírgula: separador que o Excel em português entende.
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Data", "Jogador", "Valor", "Forma", "Status", "Responsável", "Observação"])
    for r in rows:
        writer.writerow([r["date"].strftime("%d/%m/%Y") if r["date"] else "", r["player"],
                         cents_to_input(r["amount"]), r["method"], "Pago" if r["paid"] else "Pendente",
                         r["by"], r["note"]])
    # "﻿" (BOM) faz o Excel reconhecer os acentos corretamente.
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="quadrapro-{month.key}.csv"'})


# ------------------------------ Quadra e jogos ------------------------------

@bp.route("/quadra")
@login_required
def court():
    team = get_team()
    month = MonthRef.current()
    summary = month_summary(team, month)
    game = next_game(team.game_weekday, team.game_start)
    return render_template("court.html", team=team, summary=summary, month=month, game=game,
                           nav="quadra")


@bp.route("/quadra/editar", methods=["GET", "POST"])
@login_required
def court_edit():
    team = get_team()
    form = TeamForm(obj=team)
    if request.method == "GET":
        form.court_cost.data = cents_to_input(team.court_cost_cents)
        form.price_per_player.data = cents_to_input(team.price_per_player_cents)
        form.game_weekday.data = "" if team.game_weekday is None else str(team.game_weekday)
    if form.validate_on_submit():
        team.name = form.name.data.strip()
        team.description = (form.description.data or "").strip()
        team.court_name = (form.court_name.data or "").strip()
        team.court_address = (form.court_address.data or "").strip()
        team.court_cost_cents = form.court_cost.cents
        team.price_per_player_cents = form.price_per_player.cents
        team.game_weekday = int(form.game_weekday.data) if form.game_weekday.data else None
        team.game_start = form.game_start.data or ""
        team.game_end = form.game_end.data or ""
        # Limita a 20 regras, uma por linha.
        team.rules = "\n".join([r.strip()[:100] for r in (form.rules.data or "").splitlines() if r.strip()][:20])
        db.session.commit()
        flash("Dados do time e da quadra atualizados!", "success")
        return redirect(url_for("main.court"))
    return render_template("court_form.html", form=form, nav="quadra")


# ------------------------------ Notificações ------------------------------

@bp.route("/notificacoes")
@login_required
def notifications():
    team = get_team()
    items = (Notification.query.filter_by(team_id=team.id)
             .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(50).all())
    unread_ids = {n.id for n in items if not n.read}
    game = next_game(team.game_weekday, team.game_start)
    # Lembrete automático: só aparece se o jogo for nos próximos 3 dias.
    show_reminder = game is not None and game - datetime.now() <= timedelta(days=3)
    summary = month_summary(team, MonthRef.current())
    # Ao abrir a tela, os avisos passam a contar como lidos.
    if unread_ids:
        Notification.query.filter(Notification.id.in_(unread_ids)).update({"read": True})
        db.session.commit()
    return render_template("notifications.html", items=items, unread_ids=unread_ids, game=game,
                           show_reminder=show_reminder,
                           summary=summary, team=team, clear_form=EmptyForm(), nav="notificacoes")


@bp.post("/notificacoes/limpar")
@login_required
def notifications_clear():
    team = get_team()
    if EmptyForm().validate_on_submit():
        Notification.query.filter_by(team_id=team.id).delete()
        db.session.commit()
        flash("Notificações apagadas.", "success")
    return redirect(url_for("main.notifications"))


# ------------------------------ Configurações ------------------------------

@bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
def settings():
    team = get_team()
    account_form = AccountForm(obj=current_user, prefix="conta")
    password_form = ChangePasswordForm(prefix="senha")
    delete_form = DeleteAccountForm(prefix="excluir")

    # Cada formulário tem seu próprio botão; o prefixo diz qual foi enviado.
    if request.method == "POST":
        if "conta-submit" in request.form and account_form.validate_on_submit():
            email = account_form.email.data.strip().lower()
            other = User.query.filter(User.email == email, User.id != current_user.id).first()
            if other:
                account_form.email.errors.append("Este e-mail já está em uso.")
            else:
                current_user.name = account_form.name.data.strip()
                current_user.email = email
                db.session.commit()
                flash("Dados da conta atualizados!", "success")
                return redirect(url_for("main.settings"))
        elif "senha-submit" in request.form and password_form.validate_on_submit():
            if not current_user.check_password(password_form.current.data):
                password_form.current.errors.append("Senha atual incorreta.")
            else:
                current_user.set_password(password_form.password.data)
                db.session.commit()
                flash("Senha alterada!", "success")
                return redirect(url_for("main.settings"))
        elif "excluir-submit" in request.form and delete_form.validate_on_submit():
            if not current_user.check_password(delete_form.password.data):
                delete_form.password.errors.append("Senha incorreta.")
            else:
                user = db.session.get(User, current_user.id)
                logout_user()
                # Apaga o usuário, o time, jogadores, pagamentos e avisos (cascata).
                db.session.delete(user)
                db.session.commit()
                flash("Sua conta e todos os dados foram excluídos.", "info")
                return redirect(url_for("auth.login"))

    return render_template("settings.html", team=team, account_form=account_form,
                           password_form=password_form, delete_form=delete_form,
                           nav="configuracoes")


# ------------------------------ Compartilhar resumo ------------------------------

def summary_text(team: Team, month: MonthRef, summary) -> str:
    """Texto do resumo do mês, pronto para colar no grupo do WhatsApp."""
    lines = [f"⚽ *{team.name}* — Resumo de {month.label}", ""]
    if team.price_per_player_cents:
        lines.append(f"Valor por jogador: {format_cents(team.price_per_player_cents)}")
    lines += [
        f"✅ Pagaram: {summary.paid_count} jogador(es)",
        f"❌ Pendentes: {summary.pending_count} jogador(es)",
        "",
        f"💰 Arrecadado: {format_cents(summary.collected_cents)}",
        f"⏳ Pendente: {format_cents(summary.pending_cents)}",
    ]
    if team.court_cost_cents:
        lines.append(f"🏟️ Valor da quadra: {format_cents(team.court_cost_cents)}")
    if summary.pending_players:
        lines += ["", "*Lista de pendentes:*"]
        lines += [f"• {p.name} — {format_cents(p.amount_cents)}" for p in summary.pending_players]
    game = next_game(team.game_weekday, team.game_start)
    if game:
        lines += ["", f"📅 Próximo jogo: {long_date(game)} às {team.game_start}"
                  + (f" — {team.court_name}" if team.court_name else "")]
    lines += ["", "Enviado pelo QuadraPro"]
    return "\n".join(lines)


@bp.route("/compartilhar")
@login_required
def share():
    team = get_team()
    month = selected_month()
    summary = month_summary(team, month)
    text = summary_text(team, month, summary)
    whatsapp_url = "https://wa.me/?text=" + quote(text)
    return render_template("share.html", team=team, month=month, summary=summary, text=text,
                           whatsapp_url=whatsapp_url, can_next=can_go_next(month), nav="inicio")


# ------------------------------ Páginas públicas ------------------------------

@bp.route("/termos")
def terms():
    return render_template("legal/terms.html")


@bp.route("/privacidade")
def privacy():
    return render_template("legal/privacy.html")
