"""Extrator por regras: determinístico, offline, custo zero. É o padrão.

Trabalha sobre a estrutura que a Lei 14.133/2021 induz nos editais:
seções numeradas com títulos previsíveis ("DO OBJETO", "DA GARANTIA
CONTRATUAL") e fórmulas consagradas ("tem por objeto a", "valor estimado
da contratação é de"). Cada campo devolve o trecho de onde saiu, então a
prova vem de graça: o trecho é, por construção, texto do edital.

O que ele NÃO faz: entender redação fora do padrão. Se um edital escrever
"caucionamento prévio de proposta" em vez de "garantia de proposta", o
campo sai como nao_encontrado, nunca como um chute.
"""

import re

import contrato
from contrato import AUSENTE_DECLARADO, ENCONTRADO, NAO_ENCONTRADO, campo

DINHEIRO = r"R\$\s*[\d.]+,\d{2}"
PERCENTUAL = r"\d+(?:,\d+)?\s*%"


def _secao(texto, titulo):
    """Devolve o bloco de uma seção numerada, do título até a próxima."""
    padrao = rf"^\d+\.\s+{titulo}\b.*?(?=^\d+\.\s+[A-ZÀ-Ü]|\Z)"
    m = re.search(padrao, texto, re.M | re.S)
    return m.group(0) if m else None


def _linha_de(texto, posicao_inicio, posicao_fim):
    """A(s) linha(s) completa(s) que contêm o intervalo casado."""
    inicio = texto.rfind("\n", 0, posicao_inicio) + 1
    fim = texto.find("\n", posicao_fim)
    if fim == -1:
        fim = len(texto)
    return texto[inicio:fim].strip()


def _frase_de(texto, m):
    """A frase inteira em volta de um casamento: do início do item ao ponto final."""
    inicio = texto.rfind("\n", 0, m.start()) + 1
    fim = texto.find(".\n", m.end())
    if fim == -1:
        fim = len(texto)
    else:
        fim += 1
    return re.sub(r"\s+", " ", texto[inicio:fim]).strip()


def _orgao(texto):
    primeira_linha = texto.strip().splitlines()[0].strip()
    if primeira_linha:
        return campo(ENCONTRADO, primeira_linha, primeira_linha)
    return campo(NAO_ENCONTRADO)


def _numero_e_modalidade(texto):
    m = re.search(r"EDITAL DE ([A-ZÀ-Ü ]+?) Nº (\d+/\d{4})", texto)
    if not m:
        return campo(NAO_ENCONTRADO), campo(NAO_ENCONTRADO)
    trecho = _linha_de(texto, m.start(), m.end())
    return (
        campo(ENCONTRADO, m.group(2), trecho),
        campo(ENCONTRADO, m.group(1).strip(), trecho),
    )


def _objeto(texto):
    m = re.search(r"tem por objeto a (.+?)[,.]?\s*conforme", texto, re.S)
    if not m:
        m = re.search(r"tem por objeto a (.+?)\.", texto, re.S)
    if not m:
        return campo(NAO_ENCONTRADO)
    valor = re.sub(r"\s+", " ", m.group(1)).strip()
    return campo(ENCONTRADO, valor, _frase_de(texto, m))


def _valor_estimado(texto):
    m = re.search(rf"valor estimado da contratação é de ({DINHEIRO})", texto)
    if not m:
        return campo(NAO_ENCONTRADO)
    return campo(ENCONTRADO, m.group(1), _frase_de(texto, m))


def _data_sessao(texto):
    m = re.search(r"sessão pública[^.]*?no dia (\d{2}/\d{2}/\d{4})", texto, re.S)
    if not m:
        return campo(NAO_ENCONTRADO)
    return campo(ENCONTRADO, m.group(1), _frase_de(texto, m))


def _garantia(secao):
    """Percentual e valor absoluto dentro de uma seção de garantia."""
    percentual = campo(NAO_ENCONTRADO)
    valor = campo(NAO_ENCONTRADO)
    m = re.search(rf"({PERCENTUAL})", secao)
    if m:
        percentual = campo(ENCONTRADO, m.group(1).replace(" ", ""),
                           _frase_de(secao, m))
    m = re.search(rf"correspondente a ({DINHEIRO})", secao)
    if m:
        valor = campo(ENCONTRADO, m.group(1), _frase_de(secao, m))
    return percentual, valor


def _garantia_proposta(texto):
    secao = _secao(texto, "DA GARANTIA DE PROPOSTA")
    if secao is None:
        return campo(NAO_ENCONTRADO), campo(NAO_ENCONTRADO)
    m = re.search(r"[Nn]ão será exigida garantia de proposta", secao)
    if m:
        trecho = _frase_de(secao, m)
        return (campo(AUSENTE_DECLARADO, trecho=trecho),
                campo(AUSENTE_DECLARADO, trecho=trecho))
    return _garantia(secao)


def _garantia_contratual(texto):
    secao = _secao(texto, "DA GARANTIA CONTRATUAL")
    if secao is None:
        tres = campo(NAO_ENCONTRADO)
        return tres, dict(tres), dict(tres), dict(tres)

    # Dispensa declarada vale para a seção inteira: sem garantia não há
    # percentual, valor, prazo nem modalidade a discutir.
    m = re.search(r"[Nn]ão será exigida garantia", secao)
    if m:
        dispensada = campo(AUSENTE_DECLARADO, trecho=_frase_de(secao, m))
        return (dict(dispensada), dict(dispensada), dict(dispensada),
                dict(dispensada))

    percentual, valor = _garantia(secao)

    # A prova do "sim" é a menção; a prova do "nao" é a frase que lista
    # as modalidades admitidas sem citar o seguro-garantia. Trecho
    # inventado não serve de prova: a conferência exige texto do edital.
    m = re.search(r"seguro-garantia", secao)
    modalidades = re.search(r"modalidades de garantia", secao)
    if m:
        aceito = campo(ENCONTRADO, "sim", _frase_de(secao, m))
    elif modalidades:
        aceito = campo(ENCONTRADO, "nao", _frase_de(secao, modalidades))
    else:
        aceito = campo(NAO_ENCONTRADO)

    m = re.search(r"prazo de (\d+) \([^)]+\)\s+dias", secao)
    if m:
        prazo = campo(ENCONTRADO, m.group(1), _frase_de(secao, m))
    else:
        prazo = campo(NAO_ENCONTRADO)

    return percentual, valor, aceito, prazo


def _vigencia(texto):
    m = re.search(r"vigência de (\d+) \([^)]+\)\s+meses", texto)
    if not m:
        return campo(NAO_ENCONTRADO)
    return campo(ENCONTRADO, m.group(1), _frase_de(texto, m))


def extrair(texto):
    """Edital (texto puro) -> extração no formato do contrato."""
    extracao = contrato.vazio()

    extracao["orgao"] = _orgao(texto)
    extracao["numero_edital"], extracao["modalidade"] = _numero_e_modalidade(texto)
    extracao["objeto"] = _objeto(texto)
    extracao["valor_estimado"] = _valor_estimado(texto)
    extracao["data_sessao"] = _data_sessao(texto)

    proposta_pct, proposta_valor = _garantia_proposta(texto)
    extracao["garantia_proposta_percentual"] = proposta_pct
    extracao["garantia_proposta_valor"] = proposta_valor

    contratual_pct, contratual_valor, aceito, prazo = _garantia_contratual(texto)
    extracao["garantia_contratual_percentual"] = contratual_pct
    extracao["garantia_contratual_valor"] = contratual_valor
    extracao["seguro_garantia_aceito"] = aceito
    extracao["prazo_apresentacao_garantia_dias"] = prazo

    extracao["prazo_vigencia_meses"] = _vigencia(texto)

    return extracao
