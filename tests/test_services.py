"""Testes das regras de negócio: dinheiro, meses e cálculo do mês."""
from datetime import datetime
from types import SimpleNamespace

from app.services.money import cents_to_input, format_cents, parse_cents
from app.services.months import MonthRef, long_date, next_game
from app.services.summary import compute_summary


def test_parse_cents_formatos():
    assert parse_cents("20") == 2000
    assert parse_cents("20,5") == 2050
    assert parse_cents("20,50") == 2050
    assert parse_cents("R$ 1.234,56") == 123456
    assert parse_cents("20.50") == 2050
    assert parse_cents("1.000") == 100000
    assert parse_cents("") is None
    assert parse_cents("abc") is None


def test_format_cents():
    assert format_cents(2000) == "R$ 20,00"
    assert format_cents(123456) == "R$ 1.234,56"
    assert format_cents(0) == "R$ 0,00"
    for c in (0, 5, 2000, 123456):
        assert parse_cents(cents_to_input(c)) == c


def test_meses_e_virada_de_ano():
    dez = MonthRef(2026, 12)
    assert dez.key == "2026-12"
    assert dez.label == "Dezembro 2026"
    assert dez.next == MonthRef(2027, 1)
    assert MonthRef(2027, 1).previous == dez
    assert MonthRef.parse("2026-03") == MonthRef(2026, 3)
    assert MonthRef.parse("lixo") == MonthRef.current()


def test_proximo_jogo():
    # Segunda-feira, 19/10/2026, 10h. Jogo aos sábados às 19h -> sábado 24/10.
    now = datetime(2026, 10, 19, 10, 0)
    assert next_game(5, "19:00", now) == datetime(2026, 10, 24, 19, 0)
    # No próprio sábado depois das 19h -> sábado seguinte.
    assert next_game(5, "19:00", datetime(2026, 10, 24, 21, 0)) == datetime(2026, 10, 31, 19, 0)
    assert next_game(None, "19:00", now) is None
    assert long_date(datetime(2026, 10, 24)) == "Sábado, 24 de outubro"


def _player(i, amount=2000, active=True):
    return SimpleNamespace(id=i, amount_cents=amount, active=active, name=f"J{i}")


def _payment(player_id, amount=2000):
    return SimpleNamespace(player_id=player_id, amount_cents=amount)


def test_exemplo_do_enunciado():
    """12 jogadores de R$ 20, 8 pagaram -> R$ 160 arrecadado e R$ 80 pendente."""
    players = [_player(i) for i in range(12)]
    payments = [_payment(i) for i in range(8)]
    s = compute_summary(players, payments)
    assert s.collected_cents == 16000
    assert s.pending_cents == 8000
    assert s.expected_cents == 24000
    assert (s.paid_count, s.pending_count, s.total_players) == (8, 4, 12)
    assert s.percent_paid == 67
    assert [p.id for p in s.pending_players] == [8, 9, 10, 11]


def test_inativos_e_removidos():
    players = [_player(1), _player(2, active=False)]
    # Pagamento de jogador removido (player_id None) ainda conta como arrecadado.
    s = compute_summary(players, [_payment(None, 2500)])
    assert s.collected_cents == 2500
    assert s.pending_cents == 2000
    assert s.total_players == 1
