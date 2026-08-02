"""Lê config/empresa.yml.

Este é o único lugar do projeto que sabe o nome da empresa.
Em qualquer outro arquivo, use:

    from config import EMPRESA
    print(f"Parecer da {EMPRESA['nome']}")
"""

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_CONFIG = RAIZ / "config" / "empresa.yml"

with open(CAMINHO_CONFIG, encoding="utf-8") as arquivo:
    _config = yaml.safe_load(arquivo)

EMPRESA = _config["empresa"]
SINTETICO = _config["dados"]["sintetico"]

# Trava de segurança: enquanto o repositório for público, o dado é sintético.
# Se alguém trocar isso sem trocar a visibilidade do repo, o projeto para.
if not SINTETICO:
    raise RuntimeError(
        "config/empresa.yml está com sintetico: false. "
        "Dado real não roda em repositório público. "
        "Torne o repositório privado antes de mudar essa chave."
    )

PASTA_EDITAIS = RAIZ / "editais"
PASTA_GABARITO = PASTA_EDITAIS / "gabarito"
