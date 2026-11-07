"""Institutional HTML templates for VR01 client communication."""
from __future__ import annotations

from html import escape


def assunto_vr01(chamado_id: int, cliente: str = "SUPERMERCADOS MAMBO") -> str:
    return f"[VR | Inclusão de Estabelecimento | {cliente} | CN: {int(chamado_id)}]"


def _html(conteudo: str) -> str:
    return ('<!doctype html><html lang="pt-BR"><body style="font-family:Arial,Helvetica,sans-serif;'
            'font-size:14px;line-height:1.6;color:#253044;max-width:680px">'
            + conteudo + '<p>Atenciosamente,</p><p><strong>Equipe EDI | NETUNNA</strong><br>'
            'Integração e Conciliação Eletrônica de Dados<br>'
            '<a href="https://www.netunna.com.br">www.netunna.com.br</a></p></body></html>')


def mensagem_autorizacao(chamado_id: int, cnpj: str = "71.676.316/0033-23",
                          cliente: str = "SUPERMERCADOS MAMBO") -> str:
    cliente, cnpj = escape(cliente), escape(cnpj)
    return _html(f"""<p>Olá, Time {cliente}, tudo bem?</p>
<p>Para darmos continuidade ao processo de integração dos arquivos de vendas e pagamentos da <strong>VR Benefícios</strong>, precisamos que seja realizada a habilitação da <strong>NETUNNA</strong> como conciliadora no Portal VR.</p>
<p><strong>Estabelecimento:</strong> {cliente}<br><strong>CNPJ:</strong> {cnpj}<br><strong>Chamado NETUNNA:</strong> #{int(chamado_id)}</p>
<p><strong>Como realizar a habilitação:</strong></p>
<ol><li>Acesse o <strong>Portal VR Benefícios</strong>.</li><li>No menu principal, selecione <strong>Financeiro</strong>.</li><li>Acesse <strong>Conciliação</strong>.</li><li>Selecione <strong>NETUNNA</strong> como parceira responsável pelo recebimento dos arquivos EDI.</li><li>Confirme a seleção e finalize a habilitação.</li></ol>
<p>Após a conclusão, pedimos a gentileza de <strong>responder a este e-mail confirmando a autorização</strong>, para que possamos acompanhar a disponibilização dos arquivos junto à VR Benefícios.</p>
<p>Agradecemos pela colaboração e permanecemos à disposição.</p>""")


def mensagem_followup(chamado_id: int, cnpj: str = "71.676.316/0033-23",
                       cliente: str = "SUPERMERCADOS MAMBO") -> str:
    cliente, cnpj = escape(cliente), escape(cnpj)
    return _html(f"""<p>Olá, Time {cliente}, tudo bem?</p>
<p>Retomamos nossa solicitação de habilitação da <strong>NETUNNA</strong> como conciliadora no Portal VR Benefícios.</p>
<p><strong>Estabelecimento:</strong> {cliente}<br><strong>CNPJ:</strong> {cnpj}<br><strong>Chamado NETUNNA:</strong> #{int(chamado_id)}</p>
<p>Para concluir, acesse <strong>Portal VR → Financeiro → Conciliação</strong>, selecione <strong>NETUNNA</strong> como conciliadora e confirme a habilitação.</p>
<p>Por gentileza, poderia nos informar se a autorização já foi realizada? Caso esteja pendente ou tenha encontrado alguma dificuldade, basta responder a este e-mail para que possamos ajudar.</p>
<p>Agradecemos pelo retorno.</p>""")
