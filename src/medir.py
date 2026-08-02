"""Mede o extrator por regras contra o gabarito dos três editais.

    python src/medir.py

O gabarito (editais/gabarito/*.json) diz, campo a campo, o status e o
valor esperados. A medição compara os dois e ainda confere se a
conferência pegou os defeitos plantados:

    edital_002   5% de R$ 1.847.520,00 não é R$ 97.376,00
    edital_003   31/06/2026 é uma data que não existe

e se NÃO acusou nada no edital limpo (falso alarme também é derrota).
"""

import json
from pathlib import Path

import config
import contrato
import extrator_regras


def comparar(nome_edital):
    texto = (config.PASTA_EDITAIS / f"{nome_edital}.txt").read_text(encoding="utf-8")
    esperado = json.loads(
        (config.PASTA_GABARITO / f"{nome_edital}.json").read_text(encoding="utf-8")
    )
    extracao = extrator_regras.extrair(texto)
    achados = contrato.validar(extracao, texto)

    divergencias = []
    for campo_nome, item_esperado in esperado["campos"].items():
        obtido = extracao[campo_nome]
        if obtido["status"] != item_esperado["status"]:
            divergencias.append(
                f"{campo_nome}: status {obtido['status']!r}, "
                f"esperado {item_esperado['status']!r}"
            )
        elif obtido["valor"] != item_esperado["valor"]:
            divergencias.append(
                f"{campo_nome}: valor {obtido['valor']!r}, "
                f"esperado {item_esperado['valor']!r}"
            )

    campos_certos = len(esperado["campos"]) - len(divergencias)
    return campos_certos, len(esperado["campos"]), divergencias, achados, esperado


def main():
    total_certos = 0
    total_campos = 0
    conferencia_ok = True

    for caminho in sorted(config.PASTA_GABARITO.glob("*.json")):
        nome = caminho.stem
        certos, quantos, divergencias, achados, esperado = comparar(nome)
        total_certos += certos
        total_campos += quantos

        print(f"{nome}: {certos}/{quantos} campos iguais ao gabarito")
        for divergencia in divergencias:
            print(f"  != {divergencia}")

        esperados = esperado["achados_esperados"]
        obtidos = [(a["campo"], a["gravidade"]) for a in achados]
        if sorted(obtidos) == sorted((a["campo"], a["gravidade"]) for a in esperados):
            if achados:
                for a in achados:
                    print(f"  conferência pegou: {a['mensagem']}")
            else:
                print("  conferência limpa, como esperado")
        else:
            conferencia_ok = False
            print(f"  CONFERÊNCIA ERROU: esperado {esperados}, obtido {achados}")

    print()
    print(f"total: {total_certos}/{total_campos} campos")
    print("conferência: " + ("todos os defeitos plantados pegos, zero falso alarme"
                             if conferencia_ok else "DIVERGÊNCIA, ver acima"))
    return 0 if (total_certos == total_campos and conferencia_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
