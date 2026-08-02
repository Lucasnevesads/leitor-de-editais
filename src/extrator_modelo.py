"""Extrator por modelo: opcional, só roda com chave em variável de ambiente.

A tese do projeto vale dobrado aqui: o valor não está em chamar a API,
está no contrato de saída e na conferência. Por isso este arquivo tem
duas metades com naturezas diferentes:

  extrair()                faz a chamada. Está escrita e NÃO foi executada
                           neste repositório (não há chave envolvida no
                           desenvolvimento). Declarado no README.
  interpretar_resposta()   transforma o que o modelo devolveu numa
                           extração no formato do contrato, sem confiar
                           em nada. É pura, sem rede, e é o que os
                           testes exercitam de verdade.

A chamada pede a resposta com structured outputs (output_config.format
com JSON schema), o que elimina uma classe de lixo: JSON malformado.
Não elimina as outras: valor que não bate com o trecho, trecho que não
existe no edital, status trocado. Essas passam pela mesma conferência
do extrator por regras, em contrato.validar().

A chave NUNCA entra no repositório: só ANTHROPIC_API_KEY no ambiente.
A dependência (anthropic) fica em requirements-modelo.txt e só é
importada dentro de extrair(), para o caminho padrão continuar leve.
"""

import json
import os

import contrato
from contrato import ENCONTRADO, NAO_ENCONTRADO, campo

MODELO = "claude-opus-5"

INSTRUCOES = """Você extrai dados de editais de licitação regidos pela \
Lei 14.133/2021 para uma corretora de seguro garantia.

Regras que não se negociam:
- Para cada campo, escolha UM status:
  "encontrado": o edital responde. Preencha valor e trecho.
  "ausente_declarado": o edital diz explicitamente que aquilo não se \
aplica ou não será exigido. Deixe valor nulo e preencha trecho com a \
frase que declara a ausência.
  "nao_encontrado": o edital não fala nada. Deixe valor e trecho nulos.
- O trecho é prova: copie LITERALMENTE do edital a frase de onde a \
informação saiu. Nunca resuma nem parafraseie o trecho.
- O valor é o texto como aparece no edital: "R$ 4.280.000,00", "5%", \
"15/09/2026", "12". Para seguro_garantia_aceito use "sim" ou "nao".
- Nunca deduza um valor que o edital não afirma. Na dúvida entre \
"encontrado" e "nao_encontrado", use "nao_encontrado"."""


def _propriedade_campo():
    return {
        "type": "object",
        "properties": {
            "status": {"enum": sorted(contrato.STATUS_VALIDOS)},
            "valor": {"type": ["string", "null"]},
            "trecho": {"type": ["string", "null"]},
        },
        "required": ["status", "valor", "trecho"],
        "additionalProperties": False,
    }


ESQUEMA_RESPOSTA = {
    "type": "object",
    "properties": {nome: _propriedade_campo() for nome in contrato.CAMPOS},
    "required": list(contrato.CAMPOS),
    "additionalProperties": False,
}


def montar_pedido(texto_edital):
    rotulos = "\n".join(
        f"- {nome}: {definicao['rotulo']}"
        for nome, definicao in contrato.CAMPOS.items()
    )
    return (
        f"Campos a extrair:\n{rotulos}\n\n"
        f"Edital:\n<edital>\n{texto_edital}\n</edital>"
    )


def texto_da_resposta(resposta):
    """Tira o texto da resposta da API, tratando os finais anormais."""
    if resposta.stop_reason == "refusal":
        raise ErroDeExtracao("o modelo recusou a solicitação")
    if resposta.stop_reason == "max_tokens":
        raise ErroDeExtracao(
            "resposta truncada por limite de tokens: não confiar em JSON parcial"
        )
    for bloco in resposta.content:
        if bloco.type == "text":
            return bloco.text
    raise ErroDeExtracao("a resposta não trouxe bloco de texto")


class ErroDeExtracao(RuntimeError):
    """A chamada não produziu uma resposta utilizável."""


def interpretar_resposta(bruto, texto_edital):
    """Resposta do modelo (str) -> (extração validável, problemas).

    Nunca levanta exceção por causa do CONTEÚDO: lixo vira campo
    nao_encontrado mais um problema registrado, porque o parecer precisa
    sair mesmo quando o modelo falha, dizendo o que não deu para ler.

    O rebaixamento é deliberado: um campo "encontrado" cujo trecho não
    existe no edital é uma alucinação, e alucinação não entra em parecer
    nem como valor suspeito. Vira nao_encontrado, com o problema anotado.
    """
    problemas = []
    extracao = contrato.vazio()

    try:
        dados = json.loads(bruto)
    except (json.JSONDecodeError, TypeError):
        problemas.append("a resposta do modelo não é JSON válido")
        return extracao, problemas
    if not isinstance(dados, dict):
        problemas.append("a resposta do modelo não é um objeto JSON")
        return extracao, problemas

    for nome_extra in sorted(set(dados) - set(contrato.CAMPOS)):
        problemas.append(f"campo fora do contrato ignorado: {nome_extra}")

    texto_normalizado = contrato.normalizar_espacos(texto_edital)

    for nome in contrato.CAMPOS:
        item = dados.get(nome)
        if not isinstance(item, dict):
            problemas.append(f"{nome}: ausente ou fora do formato na resposta")
            continue

        status = item.get("status")
        valor = item.get("valor")
        trecho = item.get("trecho")

        if status not in contrato.STATUS_VALIDOS:
            problemas.append(f"{nome}: status desconhecido {status!r}")
            continue

        if status == ENCONTRADO:
            if not isinstance(valor, str) or not valor.strip():
                problemas.append(f"{nome}: encontrado sem valor utilizável")
                continue
            if not isinstance(trecho, str) or not trecho.strip():
                problemas.append(f"{nome}: encontrado sem trecho de prova")
                continue
            if contrato.normalizar_espacos(trecho) not in texto_normalizado:
                problemas.append(
                    f"{nome}: o trecho citado não existe no edital "
                    "(valor descartado)"
                )
                continue
            extracao[nome] = campo(ENCONTRADO, valor.strip(), trecho.strip())
            continue

        # ausente_declarado exige a frase que declara; sem ela, é só silêncio.
        if status == contrato.AUSENTE_DECLARADO:
            if not isinstance(trecho, str) or (
                contrato.normalizar_espacos(trecho) not in texto_normalizado
            ):
                problemas.append(
                    f"{nome}: ausência declarada sem frase do edital que a prove "
                    "(rebaixado para nao_encontrado)"
                )
                continue
            extracao[nome] = campo(contrato.AUSENTE_DECLARADO, trecho=trecho.strip())
            continue

        extracao[nome] = campo(NAO_ENCONTRADO)

    return extracao, problemas


def extrair(texto_edital):
    """Edital -> extração, chamando a API da Anthropic.

    ESCRITA E NÃO EXECUTADA neste repositório: exige ANTHROPIC_API_KEY
    no ambiente, e o desenvolvimento foi feito sem chave. O que está
    testado é tudo que vem depois da rede: texto_da_resposta(),
    interpretar_resposta() e contrato.validar().
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ErroDeExtracao(
            "ANTHROPIC_API_KEY não está no ambiente. O extrator por modelo é "
            "opcional; sem chave, use o extrator por regras (o padrão)."
        )

    import anthropic  # dependência opcional: requirements-modelo.txt

    cliente = anthropic.Anthropic()
    resposta = cliente.messages.create(
        model=MODELO,
        max_tokens=8192,
        system=INSTRUCOES,
        messages=[{"role": "user", "content": montar_pedido(texto_edital)}],
        output_config={
            "format": {"type": "json_schema", "schema": ESQUEMA_RESPOSTA}
        },
    )
    bruto = texto_da_resposta(resposta)
    return interpretar_resposta(bruto, texto_edital)
