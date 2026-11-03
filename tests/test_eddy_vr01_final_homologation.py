"""Final VR01 homologation: deterministic and side-effect-free."""
from scripts.eddy_vr01_final_homologation import homologar


def test_full_vr01_lifecycle_is_homologated_without_side_effects():
    result = homologar()
    assert result["resultado"] == "APROVADO"
    assert result["tipo"] == "HOMOLOGACAO_SINTETICA_SEM_EFEITOS"
    assert len(result["transicoes"]) == 9
    assert len(result["guardas_verificadas"]) == 8
    assert result["transicoes"][0]["operacao_simulada"] == "ASSUMIR_REDMINE"
    assert result["transicoes"][-1]["operacao_simulada"] == "CONCLUIDO"
    assert result["redmine_escritas"] == 0
    assert result["emails_enviados"] == 0
    assert result["mysql_escritas"] == 0
    assert result["producao_liberada"] is False
