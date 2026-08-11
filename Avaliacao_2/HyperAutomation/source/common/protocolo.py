"""
Módulo para geração de protocolos únicos e irrepetíveis.
"""
import uuid
from datetime import datetime

def gerar_protocolo_unico() -> str:
    """
    Gera um número de protocolo único e irrepetível composto por timestamp + código único de 6 caracteres hex.
    Exemplo de retorno: PROT-20260729-202510-A9C3F1
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    sufixo_hex = uuid.uuid4().hex[:6].upper()
    return f"PROT-{timestamp}-{sufixo_hex}"
