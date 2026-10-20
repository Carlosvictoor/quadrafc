"""Conversão de dinheiro.

Os valores são guardados em CENTAVOS (número inteiro) no banco, evitando
erros de arredondamento de números decimais (ex.: 0.1 + 0.2 != 0.3).
"""
import re


def format_cents(cents: int | None) -> str:
    """Converte centavos em texto de moeda. Ex.: 123456 -> "R$ 1.234,56"."""
    cents = cents or 0
    sign = "-" if cents < 0 else ""
    reais, centavos = divmod(abs(cents), 100)
    # Formata o milhar com ponto (padrão brasileiro).
    reais_txt = f"{reais:,}".replace(",", ".")
    return f"{sign}R$ {reais_txt},{centavos:02d}"


def cents_to_input(cents: int | None) -> str:
    """Valor para preencher um campo de formulário. Ex.: 2000 -> "20,00"."""
    return format_cents(cents).replace("R$ ", "")


def parse_cents(text: str | None) -> int | None:
    """Lê um valor digitado e devolve em centavos.

    Aceita "20", "20,5", "20,50", "R$ 1.234,56" e "20.50".
    Retorna None se o texto não for um valor válido.
    """
    if text is None:
        return None
    clean = re.sub(r"[^0-9,.]", "", str(text))
    if not clean:
        return None

    if "," in clean:
        # Formato brasileiro: ponto separa milhar e vírgula separa centavos.
        clean = clean.replace(".", "").replace(",", ".")
    elif "." in clean:
        # Só pontos: com 1 ou 2 dígitos depois do último é decimal ("20.50");
        # senão é separador de milhar ("1.000").
        last = clean.rfind(".")
        if len(clean) - last - 1 > 2:
            clean = clean.replace(".", "")
        else:
            clean = clean[:last].replace(".", "") + clean[last:]

    try:
        value = float(clean)
    except ValueError:
        return None
    if value < 0:
        return None
    return round(value * 100)
