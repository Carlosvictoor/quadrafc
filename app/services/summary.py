"""Cálculo dos totais de um mês: arrecadado, pendente e quem pagou.

Exemplo: 12 jogadores de R$ 20, com 8 pagos -> arrecadado R$ 160, pendente R$ 80.
"""
from dataclasses import dataclass, field


@dataclass
class MonthSummary:
    collected_cents: int = 0      # dinheiro recebido no mês
    pending_cents: int = 0        # quanto falta receber dos jogadores ativos
    expected_cents: int = 0       # total esperado (soma dos ativos)
    paid_count: int = 0           # jogadores ativos que pagaram
    pending_count: int = 0        # jogadores ativos que devem
    payments_by_player: dict = field(default_factory=dict)  # id do jogador -> Payment
    pending_players: list = field(default_factory=list)     # jogadores que devem

    @property
    def total_players(self) -> int:
        return self.paid_count + self.pending_count

    @property
    def percent_paid(self) -> int:
        """Porcentagem de jogadores que já pagaram (0 a 100)."""
        if self.total_players == 0:
            return 0
        return round(self.paid_count * 100 / self.total_players)

    def is_paid(self, player_id: int) -> bool:
        return player_id in self.payments_by_player


def compute_summary(players, payments) -> MonthSummary:
    """Calcula o resumo a partir dos jogadores e dos pagamentos do mês.

    - Arrecadado: todo pagamento do mês, mesmo de jogador removido
      ou desativado (o dinheiro entrou de verdade).
    - Pendente: soma do valor dos jogadores ATIVOS que ainda não pagaram.
    """
    s = MonthSummary()
    s.payments_by_player = {p.player_id: p for p in payments if p.player_id is not None}
    s.collected_cents = sum(p.amount_cents for p in payments)

    for player in players:
        if not player.active:
            continue
        s.expected_cents += player.amount_cents
        if player.id in s.payments_by_player:
            s.paid_count += 1
        else:
            s.pending_count += 1
            s.pending_cents += player.amount_cents
            s.pending_players.append(player)
    return s
