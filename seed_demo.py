"""Cria uma conta de DEMONSTRAÇÃO com dados de exemplo (só para testes locais).

Uso:  python seed_demo.py
Depois entre no site com:
    e-mail: demo@example.com
    senha:  demo1234
Rodar de novo apaga e recria a conta de demonstração.
"""
from datetime import date

from app import create_app
from app.extensions import db
from app.models import Payment, Player, Team, User, notify
from app.services.months import MonthRef

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

NAMES = ["Lucas Silva", "Rafael Santos", "Matheus Oliveira", "Bruno Costa", "Diego Alves",
         "Gabriel Ferreira", "Felipe Martins", "Thiago Lima", "André Souza", "Caio Rocha",
         "Pedro Henrique", "Victor Hugo"]
# Índices dos jogadores que já pagaram no mês (8 de 12, como na referência).
PAID = [0, 1, 2, 3, 7, 8, 9, 10]


def main():
    app = create_app()
    with app.app_context():
        old = User.query.filter_by(email=DEMO_EMAIL).first()
        if old:
            db.session.delete(old)
            db.session.commit()

        user = User(name="João Silva", email=DEMO_EMAIL)
        user.set_password(DEMO_PASSWORD)
        team = Team(name="Resenha FC", description="Time de amigos, grandes jogos!",
                    court_name="Quadra do Zé", court_address="Rua das Palmeiras, 123 - São Paulo/SP",
                    court_cost_cents=24000, price_per_player_cents=2000,
                    game_weekday=5, game_start="19:00", game_end="21:00")
        user.team = team
        db.session.add(user)

        month = MonthRef.current()
        players = [Player(team=team, name=n, amount_cents=2000) for n in NAMES]
        db.session.add_all(players)
        db.session.flush()
        today = date.today()
        for i in PAID:
            p = players[i]
            day = max(1, today.day - i)
            db.session.add(Payment(team=team, player=p, player_name=p.name, month_key=month.key,
                                   amount_cents=2000, method="dinheiro" if i == 2 else "pix",
                                   paid_on=date(month.year, month.month, day),
                                   registered_by=user.name))
        notify(team, "new_player", "Novo jogador", "Felipe Martins foi adicionado ao time.")
        notify(team, "payment_pending", "Pagamento pendente", "Diego Alves ainda não pagou a quadra.")
        notify(team, "payment_confirmed", "Pagamento registrado", "Lucas Silva pagou R$ 20,00 via Pix.")
        db.session.commit()
        print(f"Conta de demonstração criada: {DEMO_EMAIL}")


if __name__ == "__main__":
    main()
