"""O extrator por regras contra o gabarito, e a conferência contra os
defeitos plantados.

O que precisa ser verdade:
- cada campo sai com o status e o valor do gabarito;
- a conferência pega a divergência de R$ 5.000,00 do edital_002 e a
  data impossível do edital_003;
- no edital limpo ela não acusa nada, porque falso alarme também queima
  a confiança de quem lê o parecer.
"""

import json
import unittest

from . import base  # noqa: F401

import config
import contrato
import extrator_regras


def carregar(nome):
    texto = (config.PASTA_EDITAIS / f"{nome}.txt").read_text(encoding="utf-8")
    gabarito = json.loads(
        (config.PASTA_GABARITO / f"{nome}.json").read_text(encoding="utf-8")
    )
    return texto, gabarito


class TesteContraOGabarito(unittest.TestCase):
    def confere_edital(self, nome):
        texto, gabarito = carregar(nome)
        extracao = extrator_regras.extrair(texto)
        for campo_nome, esperado in gabarito["campos"].items():
            with self.subTest(edital=nome, campo=campo_nome):
                obtido = extracao[campo_nome]
                self.assertEqual(obtido["status"], esperado["status"])
                self.assertEqual(obtido["valor"], esperado["valor"])

    def test_edital_001(self):
        self.confere_edital("edital_001")

    def test_edital_002(self):
        self.confere_edital("edital_002")

    def test_edital_003(self):
        self.confere_edital("edital_003")

    def test_trechos_sao_prova_de_verdade(self):
        """Todo trecho devolvido pelas regras existe literalmente no edital."""
        for nome in ("edital_001", "edital_002", "edital_003"):
            texto, _ = carregar(nome)
            texto_normalizado = contrato.normalizar_espacos(texto)
            extracao = extrator_regras.extrair(texto)
            for campo_nome, item in extracao.items():
                if item["trecho"] is None:
                    continue
                with self.subTest(edital=nome, campo=campo_nome):
                    self.assertIn(
                        contrato.normalizar_espacos(item["trecho"]),
                        texto_normalizado,
                    )


class TesteConferencia(unittest.TestCase):
    def achados_de(self, nome):
        texto, _ = carregar(nome)
        extracao = extrator_regras.extrair(texto)
        return contrato.validar(extracao, texto)

    def test_edital_limpo_nao_gera_falso_alarme(self):
        self.assertEqual(self.achados_de("edital_001"), [])

    def test_divergencia_entre_percentual_e_valor(self):
        achados = self.achados_de("edital_002")
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["campo"], "garantia_contratual_valor")
        self.assertIn("R$ 92.376,00", achados[0]["mensagem"])
        self.assertIn("R$ 97.376,00", achados[0]["mensagem"])
        self.assertIn("R$ 5.000,00", achados[0]["mensagem"])

    def test_data_que_nao_existe(self):
        achados = self.achados_de("edital_003")
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["campo"], "data_sessao")

    def test_percentual_acima_do_teto_legal(self):
        """2% de garantia de proposta viola o art. 58, § 1º (teto de 1%)."""
        texto = "qualquer coisa"
        extracao = contrato.vazio()
        extracao["garantia_proposta_percentual"] = contrato.campo(
            contrato.ENCONTRADO, "2%", "qualquer coisa"
        )
        achados = contrato.validar(extracao, texto)
        self.assertEqual(len(achados), 1)
        self.assertIn("teto", achados[0]["mensagem"])


class TesteConversao(unittest.TestCase):
    def test_dinheiro(self):
        from decimal import Decimal
        self.assertEqual(
            contrato.converter("dinheiro", "R$ 1.847.520,00"),
            Decimal("1847520.00"),
        )

    def test_dinheiro_invalido(self):
        with self.assertRaises(ValueError):
            contrato.converter("dinheiro", "1.847.520")

    def test_percentual_com_virgula(self):
        from decimal import Decimal
        self.assertEqual(contrato.converter("percentual", "0,5%"), Decimal("0.5"))

    def test_data_impossivel(self):
        with self.assertRaises(ValueError):
            contrato.converter("data", "31/06/2026")

    def test_data_fora_do_formato(self):
        with self.assertRaises(ValueError):
            contrato.converter("data", "2026-06-30")


if __name__ == "__main__":
    unittest.main()
