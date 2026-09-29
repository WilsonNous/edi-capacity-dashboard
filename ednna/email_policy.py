from __future__ import annotations
"""Política global de destinatários dos e-mails operacionais da EDNNA."""
import os
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _lista_env(nome: str, padrao: str) -> list[str]:
    bruto = str(os.getenv(nome, padrao) or "")
    itens = re.split(r"[;,\n]+", bruto)
    return [x.strip().lower() for x in itens if _EMAIL_RE.match(x.strip())]


def cc_padrao_netunna() -> list[str]:
    """CC institucional: BPO + EDI + Consultores. Pode ser sobrescrito por env."""
    return _lista_env(
        "EDNNA_EMAIL_CC_PADRAO",
        "bpo@netunna.com.br;edi@netunna.com.br;consultores@netunna.com.br",
    )


def aplicar_cc_padrao(para: list[str] | None, cc: list[str] | None = None) -> list[str]:
    para_norm = {str(x).strip().lower() for x in (para or []) if str(x).strip()}
    saida: list[str] = []
    vistos: set[str] = set()
    for item in [*(cc or []), *cc_padrao_netunna()]:
        email = str(item or "").strip().lower()
        if not _EMAIL_RE.match(email) or email in para_norm or email in vistos:
            continue
        vistos.add(email)
        saida.append(email)
    return saida


def aplicar_cc_cliente(para: list[str] | None, cc: list[str] | None, cliente: str) -> list[str]:
    """CC institucional + contato principal do cliente vindo do Blueprint local."""
    base = aplicar_cc_padrao(para, cc)
    try:
        from ednna.blueprint_knowledge import emails_cliente_blueprint
        contatos = emails_cliente_blueprint(cliente, limite=1)
    except Exception as exc:
        print(f"[EDNNA] Blueprint CC | cliente={cliente} | indisponivel | {type(exc).__name__}: {exc}", flush=True)
        contatos = []
    para_norm={str(x).strip().lower() for x in (para or []) if str(x).strip()}
    vistos={str(x).strip().lower() for x in base}
    for email in contatos:
        e=str(email or '').strip().lower()
        if _EMAIL_RE.match(e) and e not in para_norm and e not in vistos:
            base.append(e); vistos.add(e)
    return base


# Políticas específicas por player/finalidade. A política deve ser aplicada
# antes da montagem final do pacote de e-mail; não substitui o pre-flight Redmine.
_POLITICAS_DESTINATARIOS = {
    ("POLICARD", "CONCILIACAO"): {
        "para_exclusivo": ["conciliacao@upbrasil.com"],
        "dominio_player": "upbrasil.com",
        "emails_player_proibidos": ["grandesredesup@upbrasil.com"],
        "fonte": "Orientação Atendimento Grande Rede UP Brasil em 14/09/2026",
    },
}

def aplicar_politica_destinatarios(
    player: str,
    finalidade: str,
    para: list[str] | None,
    cc: list[str] | None = None,
) -> tuple[list[str], list[str], dict]:
    """Aplica política vigente de destinatários sem remover contatos externos do cliente.

    Para políticas com ``para_exclusivo``, qualquer endereço do domínio do player
    é removido de CC e o destinatário oficial substitui os destinatários do player.
    Contatos do cliente e CCs institucionais Netunna permanecem permitidos.
    """
    chave=(str(player or '').strip().upper(), str(finalidade or '').strip().upper())
    politica=_POLITICAS_DESTINATARIOS.get(chave)
    para_norm=[str(x).strip().lower() for x in (para or []) if _EMAIL_RE.match(str(x).strip())]
    cc_norm=[str(x).strip().lower() for x in (cc or []) if _EMAIL_RE.match(str(x).strip())]
    if not politica:
        return para_norm, cc_norm, {"aplicada": False}

    dominio=str(politica.get("dominio_player") or '').lower()
    exclusivos=[str(x).lower() for x in politica.get("para_exclusivo", [])]
    proibidos={str(x).lower() for x in politica.get("emails_player_proibidos", [])}

    # Endereços do próprio player obedecem à rota oficial. Outros domínios
    # (cliente/Netunna) não são interpretados como proibidos por esta política.
    para_saida=[e for e in para_norm if not (dominio and e.endswith('@'+dominio)) and e not in proibidos]
    para_saida=exclusivos + [e for e in para_saida if e not in exclusivos]
    cc_saida=[e for e in cc_norm if e not in proibidos and not (dominio and e.endswith('@'+dominio)) and e not in para_saida]
    return para_saida, cc_saida, {
        "aplicada": True,
        "player": chave[0],
        "finalidade": chave[1],
        "fonte": politica.get("fonte"),
        "removidos": sorted(set(para_norm + cc_norm) - set(para_saida + cc_saida)),
    }
