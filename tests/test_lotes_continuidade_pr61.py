import unittest
from unittest.mock import patch

from ednna.lotes_continuidade import selecionar_lote_rotativo, selecionar_persistido, confirmar_lote


class TestLotesContinuidade(unittest.TestCase):
    def test_avanca_e_retorna_ao_inicio(self):
        ids = [48, 12, 35, 22, 12]
        self.assertEqual(selecionar_lote_rotativo(ids, 2), [12, 22])
        self.assertEqual(selecionar_lote_rotativo(ids, 2, 22), [35, 48])
        self.assertEqual(selecionar_lote_rotativo(ids, 2, 48), [12, 22])

    def test_limite_zero_nao_seleciona(self):
        self.assertEqual(selecionar_lote_rotativo([1, 2], 0), [])

    def test_lote_nao_repete_itens_quando_maior_que_estoque(self):
        self.assertEqual(selecionar_lote_rotativo([1, 2], 12, 1), [2, 1])

    def test_cursor_persistido(self):
        with patch("painel_cache.obter_metadado", return_value="22"):
            self.assertEqual(selecionar_persistido([12, 22, 35], 2, "chave"), [35, 12])

    def test_confirmacao_checkpoint(self):
        with patch("painel_cache.salvar_metadado") as salvar:
            confirmar_lote("chave", [35, 12])
            salvar.assert_called_once_with("chave", "12")

    def test_sem_confirmacao_para_lote_vazio(self):
        with patch("painel_cache.salvar_metadado") as salvar:
            confirmar_lote("chave", [])
            salvar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
