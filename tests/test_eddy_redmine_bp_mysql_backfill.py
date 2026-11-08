"""PR214: existing Redmine Blueprint parser must persist evidence to MySQL."""
from io import BytesIO
from unittest.mock import patch
from openpyxl import Workbook

from ednna.mysql_blueprint_participants import sincronizar_blueprints_redmine_mysql


def test_redmine_blueprint_excel_populates_mysql_evidence_without_sqlite():
    wb = Workbook()
    ws = wb.active
    ws.title = "ID PROJETO"
    ws.append(["CNPJ:", "12.345.678/0001-90"])
    ws2 = wb.create_sheet("PARTICIPANTES")
    ws2.append(["NOME", "E-MAIL", "AREA"])
    ws2.append(["Contato", "contato@example.com", "FINANCEIRO"])
    wb.create_sheet("ESTABELECIMENTOS")
    data = BytesIO()
    wb.save(data)
    issue = {"id": 900, "attachments": [{
        "id": 10, "filename": "blueprint.xlsx",
        "content_url": "https://example.invalid/file"
    }]}
    with patch("redmine_api.buscar_detalhes_chamado", return_value=issue), \
         patch("redmine_api.baixar_anexo_redmine", return_value=data.getvalue()), \
         patch("ednna.mysql_blueprint_participants.preparar"), \
         patch("ednna.mysql_blueprint_participants.connect") as db, \
         patch("ednna.eddy_blueprint_identity_evidence.registrar_bp") as registrar:
        db.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.executemany.return_value = None
        result = sincronizar_blueprints_redmine_mysql({900: "CLIENTE A"}, aplicar=True)
    assert result["resultados"][0]["status"] == "IMPORTADO"
    registrar.assert_called_once_with("CLIENTE A", 900, {"12345678000190"})
    assert result["redmine_escritas"] == 0
    assert result["emails_enviados"] == 0
