"""Meses de referência das cobranças e datas em português.

Os pagamentos são organizados por mês com a chave "AAAA-MM" (ex.: "2026-10").
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MONTH_NAMES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
               "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
# Segunda = 0 ... Domingo = 6 (mesmo padrão do Python).
WEEKDAY_NAMES = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
                 "Sexta-feira", "Sábado", "Domingo"]
WEEKDAY_SHORT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@dataclass(frozen=True, order=True)
class MonthRef:
    """Um mês de cobrança (ano + mês)."""

    year: int
    month: int

    @classmethod
    def current(cls) -> "MonthRef":
        today = date.today()
        return cls(today.year, today.month)

    @classmethod
    def parse(cls, key: str | None) -> "MonthRef":
        """Lê "2026-10". Se o texto for inválido, devolve o mês atual."""
        try:
            year, month = (int(p) for p in (key or "").split("-"))
            if 2000 <= year <= 2100 and 1 <= month <= 12:
                return cls(year, month)
        except ValueError:
            pass
        return cls.current()

    @property
    def key(self) -> str:
        return f"{self.year}-{self.month:02d}"

    @property
    def label(self) -> str:
        """Ex.: "Outubro 2026"."""
        return f"{MONTH_NAMES[self.month - 1]} {self.year}"

    @property
    def name(self) -> str:
        return MONTH_NAMES[self.month - 1]

    @property
    def next(self) -> "MonthRef":
        return MonthRef(self.year + self.month // 12, self.month % 12 + 1)

    @property
    def previous(self) -> "MonthRef":
        return MonthRef(self.year - (self.month == 1), (self.month - 2) % 12 + 1)


def next_game(weekday: int | None, start: str | None, now: datetime | None = None) -> datetime | None:
    """Calcula a data do próximo jogo semanal.

    weekday: 0 = segunda ... 6 = domingo. start: horário "19:00".
    Se o jogo de hoje ainda não começou, o próximo jogo é hoje.
    """
    if weekday is None or not start:
        return None
    now = now or datetime.now()
    try:
        hour, minute = (int(p) for p in start.split(":"))
    except ValueError:
        return None
    days_ahead = (weekday - now.weekday()) % 7
    game = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if game < now:
        game += timedelta(days=7)
    return game


def long_date(d: date | datetime) -> str:
    """Ex.: "Sábado, 25 de outubro"."""
    return f"{WEEKDAY_NAMES[d.weekday()]}, {d.day} de {MONTH_NAMES[d.month - 1].lower()}"


def short_date(d: date | datetime) -> str:
    """Ex.: "Sáb, 25 de Out"."""
    return f"{WEEKDAY_SHORT[d.weekday()]}, {d.day} de {MONTH_NAMES[d.month - 1][:3]}"
