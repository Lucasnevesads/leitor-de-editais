"""O que dá para testar do extrator por modelo SEM chamar a API: tudo
que vem depois da rede, que é onde o risco mora.

A chamada em si está escrita e não foi executada (ver README). Estes
testes exercitam:

- texto_da_resposta(): os finais anormais (recusa, truncamento, resposta
  sem texto) viram erro claro em vez de JSON parcial tratado como bom;
- interpretar_resposta(): resposta bem-formada vira extração idêntica à
  das regras, e cada tipo de lixo vira campo nao_encontrado com o
  problema anotado, nunca uma exceção nem um valor inventado no parecer.
"""

import json
import unittest

from . import base  # noqa: F401

import config
import contrato
import extrator_modelo
import extrator_regras


def edital(nome):
    return (config.PASTA_EDITAIS / f"{nome}.txt").read_text(encoding="utf-8")


def resposta_valida_para(texto):
    """Monta a resposta que um modelo perfeito daria: a mesma extração
    das regras, no formato JSON que o schema pede."""
    extracao = extrator_regras.extrair(texto)
    return json.dumps(extracao, ensure_ascii=False)


class RespostaFalsa:
    """Só o que texto_da_resposta() olha: stop_reason e content."""

    class Bloco:
        def __init__(self, tipo, texto=""):
            self.type = tipo
            self.text = texto

    def __init__(self, stop_reason="end_turn", blocos=()):
        self.stop_reason = stop_reason
        self.content = list(blocos)


class TesteTextoDaResposta(unittest.TestCase):
    def test_resposta_normal(self):
        resposta = RespostaFalsa(blocos=[RespostaFalsa.Bloco("text", "{}")])
        self.assertEqual(extrator_modelo.texto_da_resposta(resposta), "{}")

    def test_recusa(self):
        with self.assertRaises(extrator_modelo.ErroDeExtracao):
            extrator_modelo.texto_da_resposta(RespostaFalsa(stop_reason="refusal"))

    def test_truncamento_nao_vira_json_parcial(self):
        resposta = RespostaFalsa(
            stop_reason="max_tokens",
            blocos=[RespostaFalsa.Bloco("text", '{"orgao": {"sta')],
        )
        with self.assertRaises(extrator_modelo.ErroDeExtracao):
            extrator_modelo.texto_da_resposta(resposta)

    def test_sem_bloco_de_texto(self):
        with self.assertRaises(extrator_modelo.ErroDeExtracao):
            extrator_modelo.texto_da_resposta(RespostaFalsa(blocos=[]))


class TesteRespostaBemFormada(unittest.TestCase):
    def test_equivale_ao_extrator_por_regras(self):
        for nome in ("edital_001", "edital_002", "edital_003"):
            texto = edital(nome)
            extracao, problemas = extrator_modelo.interpretar_resposta(
                resposta_valida_para(texto), texto
            )
            with self.subTest(edital=nome):
                self.assertEqual(problemas, [])
                self.assertEqual(extracao, extrator_regras.extrair(texto))

    def test_passa_na_mesma_conferencia(self):
        texto = edital("edital_002")
        extracao, _ = extrator_modelo.interpretar_resposta(
            resposta_valida_para(texto), texto
        )
        achados = contrato.validar(extracao, texto)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["campo"], "garantia_contratual_valor")


class TesteModeloDevolvendoLixo(unittest.TestCase):
    """Cada tipo de lixo vira problema anotado, nunca exceção."""

    def setUp(self):
        self.texto = edital("edital_001")
        self.valida = json.loads(resposta_valida_para(self.texto))

    def interpreta(self, dados):
        bruto = dados if isinstance(dados, str) else json.dumps(
            dados, ensure_ascii=False
        )
        return extrator_modelo.interpretar_resposta(bruto, self.texto)

    def test_nao_e_json(self):
        extracao, problemas = self.interpreta("O edital exige garantia de 5%.")
        self.assertEqual(extracao, contrato.vazio())
        self.assertEqual(len(problemas), 1)

    def test_json_que_nao_e_objeto(self):
        extracao, problemas = self.interpreta('["orgao", "objeto"]')
        self.assertEqual(extracao, contrato.vazio())
        self.assertEqual(len(problemas), 1)

    def test_campo_faltando(self):
        del self.valida["orgao"]
        extracao, problemas = self.interpreta(self.valida)
        self.assertEqual(extracao["orgao"]["status"], contrato.NAO_ENCONTRADO)
        self.assertTrue(any("orgao" in p for p in problemas))

    def test_status_inventado(self):
        self.valida["orgao"]["status"] = "talvez"
        extracao, problemas = self.interpreta(self.valida)
        self.assertEqual(extracao["orgao"]["status"], contrato.NAO_ENCONTRADO)
        self.assertTrue(any("talvez" in p for p in problemas))

    def test_encontrado_sem_valor(self):
        self.valida["valor_estimado"]["valor"] = None
        extracao, problemas = self.interpreta(self.valida)
        self.assertEqual(
            extracao["valor_estimado"]["status"], contrato.NAO_ENCONTRADO
        )
        self.assertTrue(any("valor_estimado" in p for p in problemas))

    def test_valor_com_tipo_errado(self):
        self.valida["prazo_vigencia_meses"]["valor"] = 14
        extracao, problemas = self.interpreta(self.valida)
        self.assertEqual(
            extracao["prazo_vigencia_meses"]["status"], contrato.NAO_ENCONTRADO
        )
        self.assertTrue(any("prazo_vigencia_meses" in p for p in problemas))

    def test_trecho_alucinado_derruba_o_campo(self):
        """O caso que importa: valor plausível com prova que não existe."""
        self.valida["valor_estimado"]["trecho"] = (
            "O valor estimado da contratação é de R$ 4.280.000,00, "
            "conforme planilha SINAPI de junho."
        )
        extracao, problemas = self.interpreta(self.valida)
        self.assertEqual(
            extracao["valor_estimado"]["status"], contrato.NAO_ENCONTRADO
        )
        self.assertTrue(any("não existe no edital" in p for p in problemas))

    def test_ausencia_declarada_sem_prova_vira_silencio(self):
        self.valida["garantia_proposta_percentual"] = {
            "status": "ausente_declarado", "valor": None, "trecho": None,
        }
        extracao, problemas = self.interpreta(self.valida)
        self.assertEqual(
            extracao["garantia_proposta_percentual"]["status"],
            contrato.NAO_ENCONTRADO,
        )
        self.assertTrue(any("garantia_proposta_percentual" in p for p in problemas))

    def test_campo_fora_do_contrato_e_ignorado(self):
        self.valida["opiniao_do_modelo"] = {
            "status": "encontrado", "valor": "edital tranquilo", "trecho": "x",
        }
        extracao, problemas = self.interpreta(self.valida)
        self.assertNotIn("opiniao_do_modelo", extracao)
        self.assertTrue(any("opiniao_do_modelo" in p for p in problemas))

    def test_lixo_nunca_vira_achado_de_valor(self):
        """Depois do lixo, a conferência roda normalmente sobre o que sobrou."""
        self.valida["valor_estimado"]["trecho"] = "trecho que não existe"
        extracao, _ = self.interpreta(self.valida)
        achados = contrato.validar(extracao, self.texto)
        # Sem valor_estimado não há base para a conferência cruzada,
        # e nenhum outro campo do edital_001 tem problema.
        self.assertEqual(achados, [])


if __name__ == "__main__":
    unittest.main()
