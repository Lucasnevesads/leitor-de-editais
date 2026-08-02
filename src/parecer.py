"""Monta o parecer: o edital resumido para quem vai decidir se cota.

O parecer separa três coisas que costumam sair misturadas:

  o que o edital DIZ          os campos encontrados, com valor
  o que a conferência ACHOU   números que não batem, datas impossíveis
  o que o edital NÃO DIZ      silêncios que viram pergunta ao órgão

Marcadores em texto puro ([ERRO], [confirmar]) de propósito: o parecer
precisa sobreviver a qualquer terminal, e-mail ou copia-e-cola.
"""

import textwrap

import contrato
from config import EMPRESA
from contrato import AUSENTE_DECLARADO, ENCONTRADO

LARGURA = 78
COLUNA_VALOR = 38


def _linha(rotulo, valor):
    """Rótulo à esquerda, valor à direita, com quebra de linha alinhada."""
    pedacos = textwrap.wrap(str(valor), LARGURA - COLUNA_VALOR - 2) or ["—"]
    linhas = [f"  {rotulo:<{COLUNA_VALOR - 2}} {pedacos[0]}"]
    for pedaco in pedacos[1:]:
        linhas.append(f"  {'':<{COLUNA_VALOR - 2}} {pedaco}")
    return "\n".join(linhas)


def _valor_de(extracao, nome, se_ausente="—"):
    item = extracao[nome]
    if item["status"] == ENCONTRADO:
        return item["valor"]
    if item["status"] == AUSENTE_DECLARADO:
        return "não exigida (declarado no edital)"
    return se_ausente


def montar(extracao, achados, problemas_do_extrator=(), origem="regras"):
    """Extração validada -> parecer em texto puro."""
    linhas = []
    titulo = f"PARECER DE EDITAL · {EMPRESA['nome']}"
    linhas.append("=" * LARGURA)
    linhas.append(titulo)
    linhas.append(f"extrator: {origem} · dados sintéticos, órgãos fictícios")
    linhas.append("=" * LARGURA)

    linhas.append("")
    linhas.append(_linha("Órgão", _valor_de(extracao, "orgao")))
    linhas.append(_linha("Edital", _valor_de(extracao, "numero_edital")))
    linhas.append(_linha("Modalidade", _valor_de(extracao, "modalidade")))
    linhas.append(_linha("Objeto", _valor_de(extracao, "objeto")))
    linhas.append(_linha("Valor estimado", _valor_de(extracao, "valor_estimado")))
    linhas.append(_linha("Sessão pública", _valor_de(extracao, "data_sessao")))

    linhas.append("")
    linhas.append("GARANTIAS")
    linhas.append(_linha(
        "Garantia de proposta",
        _junta(extracao, "garantia_proposta_percentual", "garantia_proposta_valor"),
    ))
    linhas.append(_linha(
        "Garantia contratual",
        _junta(extracao, "garantia_contratual_percentual", "garantia_contratual_valor"),
    ))
    linhas.append(_linha(
        "Seguro-garantia aceito",
        _valor_de(extracao, "seguro_garantia_aceito"),
    ))
    linhas.append(_linha(
        "Prazo para apresentar a garantia",
        _com_sufixo(extracao, "prazo_apresentacao_garantia_dias", "dias"),
    ))
    linhas.append(_linha(
        "Vigência do contrato",
        _com_sufixo(extracao, "prazo_vigencia_meses", "meses"),
    ))

    linhas.append("")
    linhas.append("CONFERÊNCIA")
    if achados:
        for item in achados:
            rotulo = contrato.CAMPOS[item["campo"]]["rotulo"]
            linhas.append(_dobrada(f"  [ERRO] {rotulo}: {item['mensagem']}"))
    else:
        linhas.append("  nenhum problema encontrado nos campos extraídos")

    cegos = contrato.pontos_cegos(extracao)
    if cegos:
        linhas.append("")
        linhas.append("O EDITAL NÃO DIZ (confirmar com o órgão antes de cotar)")
        for nome in cegos:
            linhas.append(f"  [confirmar] {contrato.CAMPOS[nome]['rotulo']}")

    if problemas_do_extrator:
        linhas.append("")
        linhas.append("PROBLEMAS NA EXTRAÇÃO (o extrator não leu tudo)")
        for problema in problemas_do_extrator:
            linhas.append(_dobrada(f"  [extrator] {problema}"))

    linhas.append("")
    linhas.append("=" * LARGURA)
    return "\n".join(linhas)


def _dobrada(texto):
    """Quebra uma linha longa mantendo a indentação nas continuações."""
    return "\n".join(textwrap.wrap(texto, LARGURA, subsequent_indent="         "))


def _junta(extracao, nome_percentual, nome_valor):
    percentual = extracao[nome_percentual]
    valor = extracao[nome_valor]
    if percentual["status"] == AUSENTE_DECLARADO:
        return "não exigida (declarado no edital)"
    if percentual["status"] == ENCONTRADO and valor["status"] == ENCONTRADO:
        return f"{percentual['valor']} · {valor['valor']}"
    if percentual["status"] == ENCONTRADO:
        return percentual["valor"]
    if valor["status"] == ENCONTRADO:
        return valor["valor"]
    return "—"


def _com_sufixo(extracao, nome, sufixo):
    item = extracao[nome]
    if item["status"] == ENCONTRADO:
        return f"{item['valor']} {sufixo}"
    return _valor_de(extracao, nome)
