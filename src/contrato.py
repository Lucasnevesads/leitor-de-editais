"""O contrato de extração e a conferência.

Todo extrator (por regras ou por modelo) devolve o MESMO formato:
um dicionário com os 13 campos abaixo, cada um valendo

    {"status": ..., "valor": ..., "trecho": ...}

com três status possíveis:

    encontrado          o edital responde, e o trecho prova
    ausente_declarado   o edital diz explicitamente que não exige
    nao_encontrado      o edital silencia

A distinção entre os dois últimos é o coração do projeto: "não será
exigida garantia de proposta" é uma certeza; a ausência de qualquer
menção é uma pergunta a fazer ao órgão. Um parecer que trata os dois
como "campo vazio" transforma silêncio em resposta.

O valor é sempre o TEXTO BRUTO como aparece no edital ("R$ 4.280.000,00",
"5%", "15/09/2026"). Quem interpreta é a conferência, num lugar só,
igual para os dois extratores.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

ENCONTRADO = "encontrado"
AUSENTE_DECLARADO = "ausente_declarado"
NAO_ENCONTRADO = "nao_encontrado"
STATUS_VALIDOS = {ENCONTRADO, AUSENTE_DECLARADO, NAO_ENCONTRADO}

# tipo diz como a conferência interpreta o valor bruto.
# limite é o teto legal do percentual, quando houver.
CAMPOS = {
    "orgao": {"tipo": "texto", "rotulo": "Órgão licitante"},
    "numero_edital": {"tipo": "texto", "rotulo": "Número do edital"},
    "modalidade": {"tipo": "texto", "rotulo": "Modalidade"},
    "objeto": {"tipo": "texto", "rotulo": "Objeto"},
    "valor_estimado": {"tipo": "dinheiro", "rotulo": "Valor estimado"},
    "data_sessao": {"tipo": "data", "rotulo": "Sessão pública"},
    "garantia_proposta_percentual": {
        "tipo": "percentual",
        "rotulo": "Garantia de proposta (%)",
        # Art. 58, § 1º, da Lei 14.133/2021: até 1% do valor estimado.
        "limite": Decimal("1"),
        "base_legal": "art. 58, § 1º (teto de 1%)",
    },
    "garantia_proposta_valor": {"tipo": "dinheiro", "rotulo": "Garantia de proposta (R$)"},
    "garantia_contratual_percentual": {
        "tipo": "percentual",
        "rotulo": "Garantia contratual (%)",
        # Art. 98 da Lei 14.133/2021: até 5% do valor inicial do contrato
        # (o art. 99 admite até 10% em obras de grande vulto).
        "limite": Decimal("5"),
        "base_legal": "art. 98 (teto de 5%; art. 99 admite 10% em grande vulto)",
    },
    "garantia_contratual_valor": {"tipo": "dinheiro", "rotulo": "Garantia contratual (R$)"},
    "prazo_apresentacao_garantia_dias": {
        "tipo": "inteiro",
        "rotulo": "Prazo para apresentar a garantia (dias)",
    },
    "prazo_vigencia_meses": {"tipo": "inteiro", "rotulo": "Vigência do contrato (meses)"},
    "seguro_garantia_aceito": {"tipo": "booleano", "rotulo": "Seguro-garantia aceito"},
}


def campo(status, valor=None, trecho=None):
    """Monta um campo no formato do contrato."""
    return {"status": status, "valor": valor, "trecho": trecho}


def vazio():
    """Extração com todos os campos em nao_encontrado."""
    return {nome: campo(NAO_ENCONTRADO) for nome in CAMPOS}


# ---------------------------------------------------------------------
# Interpretação dos valores brutos
# ---------------------------------------------------------------------
def converter(tipo, bruto):
    """Interpreta o texto bruto extraído. Levanta ValueError se não der."""
    if not isinstance(bruto, str) or not bruto.strip():
        raise ValueError("valor vazio")
    bruto = bruto.strip()

    if tipo == "texto":
        return bruto

    if tipo == "dinheiro":
        m = re.fullmatch(r"R\$\s*([\d.]+),(\d{2})", bruto)
        if not m:
            raise ValueError(f"não parece um valor em reais: {bruto!r}")
        try:
            return Decimal(m.group(1).replace(".", "") + "." + m.group(2))
        except InvalidOperation as erro:
            raise ValueError(f"não parece um valor em reais: {bruto!r}") from erro

    if tipo == "percentual":
        m = re.fullmatch(r"(\d+(?:,\d+)?)\s*%", bruto)
        if not m:
            raise ValueError(f"não parece um percentual: {bruto!r}")
        return Decimal(m.group(1).replace(",", "."))

    if tipo == "data":
        try:
            return datetime.strptime(bruto, "%d/%m/%Y").date()
        except ValueError as erro:
            raise ValueError(
                f"data inválida ou fora do formato dd/mm/aaaa: {bruto!r}"
            ) from erro

    if tipo == "inteiro":
        if not re.fullmatch(r"\d+", bruto):
            raise ValueError(f"não parece um número inteiro: {bruto!r}")
        return int(bruto)

    if tipo == "booleano":
        if bruto.lower() in ("sim", "nao", "não"):
            return bruto.lower() == "sim"
        raise ValueError(f"esperado 'sim' ou 'nao': {bruto!r}")

    raise ValueError(f"tipo desconhecido: {tipo}")


def normalizar_espacos(texto):
    return re.sub(r"\s+", " ", texto).strip()


def reais(valor):
    inteiro, centavos = f"{valor:.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {inteiro},{centavos}"


# ---------------------------------------------------------------------
# A conferência
# ---------------------------------------------------------------------
def achado(gravidade, campo_nome, mensagem):
    return {"gravidade": gravidade, "campo": campo_nome, "mensagem": mensagem}


def validar(extracao, texto_edital):
    """Confere a extração contra si mesma e contra o texto do edital.

    Devolve a lista de achados. Não altera a extração: campo com achado
    de erro é mostrado no parecer como não confiável, mas o valor fica
    à vista para ser conferido por uma pessoa.
    """
    achados = []
    interpretados = {}
    texto_normalizado = normalizar_espacos(texto_edital)

    for nome, definicao in CAMPOS.items():
        item = extracao[nome]
        if item["status"] != ENCONTRADO:
            continue

        # O trecho é a prova: precisa existir no edital, literalmente.
        trecho = item.get("trecho")
        if not trecho or normalizar_espacos(trecho) not in texto_normalizado:
            achados.append(achado(
                "erro", nome,
                "o trecho citado como prova não consta do edital",
            ))
            continue

        try:
            interpretados[nome] = converter(definicao["tipo"], item["valor"])
        except ValueError as erro:
            achados.append(achado("erro", nome, str(erro)))

    # Percentual acima do teto legal
    for nome in ("garantia_proposta_percentual", "garantia_contratual_percentual"):
        percentual = interpretados.get(nome)
        limite = CAMPOS[nome]["limite"]
        if percentual is not None and percentual > limite:
            achados.append(achado(
                "erro", nome,
                f"{percentual}% está acima do teto da Lei 14.133/2021, "
                f"{CAMPOS[nome]['base_legal']}",
            ))

    # Percentual x valor absoluto: os dois números do edital têm que
    # contar a mesma história. A base é o valor estimado, porque o valor
    # do contrato só existe depois da adjudicação.
    base = interpretados.get("valor_estimado")
    if base is not None:
        pares = (
            ("garantia_proposta_percentual", "garantia_proposta_valor"),
            ("garantia_contratual_percentual", "garantia_contratual_valor"),
        )
        for nome_percentual, nome_valor in pares:
            percentual = interpretados.get(nome_percentual)
            declarado = interpretados.get(nome_valor)
            if percentual is None or declarado is None:
                continue
            esperado = (base * percentual / 100).quantize(Decimal("0.01"))
            diferenca = declarado - esperado
            if abs(diferenca) > Decimal("0.01"):
                achados.append(achado(
                    "erro", nome_valor,
                    f"{percentual}% de {reais(base)} é {reais(esperado)}, "
                    f"mas o edital diz {reais(declarado)} "
                    f"(diferença de {reais(abs(diferenca))})",
                ))

    return achados


def pontos_cegos(extracao):
    """Campos em que o edital silencia: perguntas a fazer ao órgão."""
    return [nome for nome in CAMPOS
            if extracao[nome]["status"] == NAO_ENCONTRADO]


def ausencias_declaradas(extracao):
    """Campos que o edital declara não exigir: certezas, não dúvidas."""
    return [nome for nome in CAMPOS
            if extracao[nome]["status"] == AUSENTE_DECLARADO]
