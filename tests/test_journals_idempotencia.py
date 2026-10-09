from unittest.mock import patch
import pandas as pd
from ednna.sincronizador_journals import processar_chamado

def test_nao_reconsulta_quando_validado():
    row = pd.Series({"#": 30846, "Alterado": "2026-10-09T18:00:00", "Autor": "Operador"})
    with patch("ednna.sincronizador_journals.chamado_precisa_analise", return_value=False):
        with patch("ednna.sincronizador_journals.buscar_detalhes_chamado") as buscar:
            resultado = processar_chamado(row, set())
    assert resultado["situacao"] == "VALIDACAO_REUTILIZADA"
    buscar.assert_not_called()
