"""Desenha as duas imagens do README.

    python docs/gerar_grafico.py

Não faz parte do produto: é documentação. Por isso o matplotlib está em
requirements-dev.txt e este arquivo vive em docs/ e não em src/.

    parecer-*.png   o parecer literal do edital_002, com o erro que a
                    conferência pegou
    estados-*.png   a matriz campo x edital com os três estados

Na matriz, a identidade de cada célula está ESCRITA nela ("ok",
"não exige", "silêncio"): cor nunca é o único código. O cinza não entra
como cor categórica (reprova no piso de chroma do validador da skill de
dataviz); o estado "não exige" é neutro de propósito, porque é assunto
resolvido. As duas cores cromáticas dizem onde olhar: azul = respondido,
laranja = silêncio que vira pergunta ao órgão.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

# Sem isso, uma linha com DOIS "R$" vira fórmula matemática: o matplotlib
# trata o par de cifrões como delimitador de mathtext e come os dois.
matplotlib.rcParams["text.parse_math"] = False

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import config  # noqa: E402
import contrato  # noqa: E402
import extrator_regras  # noqa: E402
import parecer  # noqa: E402

# Paleta validada com scripts/validate_palette.js da skill de dataviz
# (azul e laranja passam nos dois temas; o cinza é neutro, não categórico).
TEMAS = {
    "light": {
        "plano": "#f9f9f7", "surface": "#fcfcfb", "primaria": "#0b0b0b",
        "secundaria": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
        "borda": "#e1e0d9",
        "acento": "#2a78d6", "alerta": "#eb6834",
    },
    "dark": {
        "plano": "#0d0d0d", "surface": "#1a1a19", "primaria": "#ffffff",
        "secundaria": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a",
        "borda": "#2c2c2a",
        "acento": "#3987e5", "alerta": "#d95926",
    },
}

EDITAIS = ("edital_001", "edital_002", "edital_003")
COLUNAS = (
    "001 · obra de escola\n(concorrência)",
    "002 · limpeza predial\n(pregão)",
    "003 · rede de água\n(concorrência)",
)


def carregar_parecer():
    texto = (config.PASTA_EDITAIS / "edital_002.txt").read_text(encoding="utf-8")
    extracao = extrator_regras.extrair(texto)
    achados = contrato.validar(extracao, texto)
    return parecer.montar(extracao, achados)


def carregar_estados():
    estados = {}
    for nome in EDITAIS:
        texto = (config.PASTA_EDITAIS / f"{nome}.txt").read_text(encoding="utf-8")
        estados[nome] = extrator_regras.extrair(texto)
    return estados


# ---------------------------------------------------------------------
# 1. O parecer
# ---------------------------------------------------------------------
def desenhar_parecer(tema_nome, texto):
    t = TEMAS[tema_nome]
    linhas = texto.split("\n")
    altura = 0.6 + len(linhas) * 0.205

    figura, eixo = plt.subplots(figsize=(6.6, altura), dpi=170)
    figura.patch.set_facecolor(t["plano"])
    eixo.set_facecolor(t["plano"])
    eixo.set_xlim(0, 1)
    eixo.set_ylim(0, 1)
    eixo.axis("off")

    eixo.add_patch(
        FancyBboxPatch(
            (0.02, 0.03), 0.96, 0.94,
            boxstyle="round,pad=0.012,rounding_size=0.022",
            facecolor=t["surface"], edgecolor=t["borda"], linewidth=1,
            transform=eixo.transAxes,
        )
    )

    em_erro = False
    for i, linha in enumerate(linhas):
        y = 0.94 - (i + 0.5) / len(linhas) * 0.88
        # A continuação de um [ERRO] (linha dobrada) continua laranja;
        # continuação de valor comum, não.
        if linha.lstrip().startswith("[ERRO]"):
            em_erro = True
        elif not linha.startswith("         ") or not linha.strip():
            em_erro = False
        erro = em_erro
        titulo = linha.startswith(("PARECER", "GARANTIAS", "CONFERÊNCIA", "O EDITAL"))
        eixo.text(
            0.055, y, linha,
            transform=eixo.transAxes, family="monospace", fontsize=7.8,
            va="center", ha="left",
            color=t["alerta"] if erro else (
                t["primaria"] if titulo else t["secundaria"]
            ),
            fontweight="bold" if (titulo or erro) else "normal",
        )

    figura.tight_layout(pad=0.2)
    saida = RAIZ / "docs" / f"parecer-{tema_nome}.png"
    figura.savefig(saida, facecolor=t["plano"], bbox_inches="tight")
    plt.close(figura)
    return saida


# ---------------------------------------------------------------------
# 2. A matriz de estados
# ---------------------------------------------------------------------
def desenhar_estados(tema_nome, estados):
    t = TEMAS[tema_nome]
    campos = list(contrato.CAMPOS)

    figura, eixo = plt.subplots(figsize=(10, 6.4), dpi=170)
    figura.patch.set_facecolor(t["surface"])
    eixo.set_facecolor(t["surface"])
    eixo.set_xlim(0, len(EDITAIS))
    eixo.set_ylim(0, len(campos))
    eixo.invert_yaxis()
    eixo.axis("off")

    def celula(x, y, item):
        status = item["status"]
        if status == contrato.ENCONTRADO:
            cor, rotulo, alfa = t["acento"], "ok", 0.16
        elif status == contrato.AUSENTE_DECLARADO:
            cor, rotulo, alfa = t["grid"], "não exige", 0.55
        else:
            cor, rotulo, alfa = t["alerta"], "silêncio", 0.16
        eixo.add_patch(FancyBboxPatch(
            (x + 0.045, y + 0.09), 0.91, 0.82,
            boxstyle="round,pad=0,rounding_size=0.07",
            facecolor=cor, alpha=alfa, edgecolor=cor, linewidth=1.1,
            mutation_aspect=1 / 2.2,
        ))
        eixo.text(
            x + 0.5, y + 0.5, rotulo, ha="center", va="center",
            fontsize=8.6, color=t["primaria"],
            fontweight="bold" if status != contrato.ENCONTRADO else "normal",
        )

    for x, nome in enumerate(EDITAIS):
        for y, campo_nome in enumerate(campos):
            celula(x, y, estados[nome][campo_nome])

    for x, titulo in enumerate(COLUNAS):
        eixo.text(x + 0.5, -0.35, titulo, ha="center", va="bottom",
                  fontsize=9, color=t["secundaria"])
    for y, campo_nome in enumerate(campos):
        eixo.text(-0.12, y + 0.5, contrato.CAMPOS[campo_nome]["rotulo"],
                  ha="right", va="center", fontsize=8.6, color=t["secundaria"])

    eixo.set_title(
        "Campo não encontrado é diferente de campo vazio",
        color=t["primaria"], fontsize=14.5, loc="left", pad=52, fontweight="bold",
        x=-0.34,
    )
    eixo.text(
        -0.34, -0.113,
        "azul = o edital responde · neutro = o edital declara que não exige (certeza) · "
        "laranja = o edital silencia (pergunta ao órgão)",
        transform=eixo.transAxes, color=t["secundaria"], fontsize=9.2,
    )
    eixo.text(
        -0.34, -0.155,
        f"{config.EMPRESA['nome']} · editais fictícios pela estrutura da "
        "Lei 14.133/2021 · extrator por regras",
        transform=eixo.transAxes, color=t["muted"], fontsize=8.6,
    )

    figura.tight_layout()
    saida = RAIZ / "docs" / f"estados-{tema_nome}.png"
    figura.savefig(saida, facecolor=t["surface"], bbox_inches="tight")
    plt.close(figura)
    return saida


def main():
    texto_parecer = carregar_parecer()
    estados = carregar_estados()
    for tema in TEMAS:
        print("gerado:", desenhar_parecer(tema, texto_parecer))
        print("gerado:", desenhar_estados(tema, estados))


if __name__ == "__main__":
    main()
