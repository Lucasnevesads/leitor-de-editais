"""Lê um edital e imprime o parecer.

    python src/ler.py editais/edital_001.txt
    python src/ler.py editais/edital_002.txt --json
    python src/ler.py editais/edital_001.txt --extrator modelo

O extrator padrão é o de regras: determinístico, offline, custo zero.
O extrator por modelo é opcional e exige ANTHROPIC_API_KEY no ambiente.
"""

import argparse
import json
import sys
from pathlib import Path

import contrato
import extrator_modelo
import extrator_regras
import parecer


def processar(caminho, nome_extrator):
    texto = Path(caminho).read_text(encoding="utf-8")

    if nome_extrator == "modelo":
        extracao, problemas = extrator_modelo.extrair(texto)
    else:
        extracao = extrator_regras.extrair(texto)
        problemas = []

    achados = contrato.validar(extracao, texto)
    return extracao, achados, problemas


def main():
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("edital", help="caminho do edital em texto puro")
    analisador.add_argument(
        "--extrator", choices=("regras", "modelo"), default="regras",
        help="regras (padrão, offline) ou modelo (exige ANTHROPIC_API_KEY)",
    )
    analisador.add_argument(
        "--json", action="store_true",
        help="imprime a extração validada em JSON em vez do parecer",
    )
    opcoes = analisador.parse_args()

    try:
        extracao, achados, problemas = processar(opcoes.edital, opcoes.extrator)
    except extrator_modelo.ErroDeExtracao as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2

    if opcoes.json:
        saida = {
            "extracao": extracao,
            "achados": achados,
            "problemas_do_extrator": problemas,
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2))
    else:
        print(parecer.montar(extracao, achados, problemas, origem=opcoes.extrator))

    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main())
