"""
EDNNA — Inteligência Operacional EDI.

Módulos de análise e automação operacional do EDI.
"""

# v3.34.13: reforça a descoberta de respostas na Inbox sem alterar o
# email_sender.py consolidado. A instalação apenas substitui as duas rotinas
# de leitura/correlação do monitor por versões compatíveis com #ID, CN: ID e [ID].
from ednna.email_monitor_v3413 import instalar as _instalar_monitor_v3413

_instalar_monitor_v3413()
del _instalar_monitor_v3413
