"""
Módulo responsável pela validação dos documentos recebidos dos clientes (Ficha Assinada + Documentos em Único PDF).
Utiliza a biblioteca PyPDF para inspeção e validação inteligente de cada página/anexo.
"""
import os
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader


def _normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'\s+', ' ', texto).lower().strip()


class ValidadorDocumentos:
    """
    Classe responsável por aplicar as regras de negócio para verificação documental dos anexos retornados pelo cliente.
    Exige rigorosamente a presença dos 3 elementos obrigatórios:
    1. Ficha Cadastral Assinada
    2. Documento Oficial com Foto (RG / CPF / CNH / Identidade)
    3. Comprovante de Residência (Fatura / Conta de Água/Luz / Declaração)
    """
    EXTENSOES_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}

    # Palavras-chave específicas para Ficha Cadastral
    KW_FICHA = ["ficha de cadastro", "ficha cadastral", "portal fake"]

    # Palavras-chave específicas para Documento Oficial com Foto (RG / CNH / Identidade Digital)
    KW_DOC_FOTO = [
        "carteira de identidade", "registro geral", "carteira nacional", 
        "documento de identificação", "documento de identificacao", "secretaria de segurança", 
        "secretaria de seguranca", "ssp", "gov.br", "republica federativa", 
        "república federativa", "identidade", "cnh", "carteira de motorista", 
        "passaporte", "filiação", "filiacao", "validar.iti", "carteira identidade"
    ]

    # Palavras-chave específicas para Comprovante de Residência (Contas de consumo / Faturas)
    KW_COMPROVANTE = [
        "comprovante de residência", "comprovante de residencia", "comprovante de endereço", 
        "comprovante de endereco", "conta de luz", "conta de água", "conta de agua", 
        "qualidade da água", "qualidade da agua", "fatura", "histórico de consumo", 
        "distribuidora", "amazonas energia", "aguas de manaus", "águas de manaus", 
        "declaracao de residencia", "declaração de residência", "valor a pagar", "vencimento",
        "demonstrativo de consumo", "comprovante residencial"
    ]

    def validar_documentos(self, caminho_anexos: list) -> dict:
        """
        Valida se o cliente retornou todos os 3 documentos obrigatórios em formato válido (via PyPDF para PDFs).

        :param caminho_anexos: Lista de caminhos (str ou Path) dos anexos retornados pelo cliente.
        :return: Dicionário contendo o status da validação (valido: bool) e a lista de pendências.
        """
        pendencias = []
        documentos_validos = []
        tem_pdf_valido = False

        tem_ficha = False
        tem_doc_foto = False
        tem_comprovante = False

        if not caminho_anexos:
            return {
                "valido": False,
                "pendencias": ["Nenhum documento retornado pelo cliente."],
                "documentos_validos": []
            }

        paths_anexos = [Path(p) for p in caminho_anexos]

        for path in paths_anexos:
            nome_lc = _normalizar_texto(path.name)
            ext = path.suffix.lower()

            if not path.exists():
                pendencias.append(f"Arquivo não localizado: '{path.name}'.")
                continue

            if path.stat().st_size == 0:
                pendencias.append(f"O arquivo retornado '{path.name}' está vazio ou corrompido (0 bytes).")
                continue

            if ext not in self.EXTENSOES_PERMITIDAS:
                pendencias.append(f"O arquivo '{path.name}' formato '{ext}' não é aceito. Envie em PDF ou DOCX.")
                continue

            documentos_validos.append(path.name)

            # Se for PDF, analisa cada página individualmente
            if ext == ".pdf":
                try:
                    reader = PdfReader(path)
                    if len(reader.pages) == 0:
                        pendencias.append(f"O arquivo PDF '{path.name}' não possui páginas.")
                        continue
                    
                    tem_pdf_valido = True
                    for page in reader.pages:
                        raw_text = page.extract_text() or ""
                        # Normaliza texto e remove acentos para busca flexível
                        t = _normalizar_texto(raw_text)

                        # Identifica se é a página da Ficha de Cadastro
                        is_ficha = any(_normalizar_texto(kw) in t for kw in self.KW_FICHA) or (
                            "ficha" in nome_lc and "assin" in t and
                            not any(_normalizar_texto(kw) in t for kw in self.KW_DOC_FOTO) and
                            not any(_normalizar_texto(kw) in t for kw in self.KW_COMPROVANTE)
                        )
                        if is_ficha:
                            tem_ficha = True

                        # Identifica se é a página de Documento Oficial com Foto
                        if any(_normalizar_texto(kw) in t for kw in self.KW_DOC_FOTO) or any(kw in nome_lc for kw in ["rg", "cnh", "identidade"]):
                            tem_doc_foto = True

                        # Identifica se é a página de Comprovante de Residência
                        if any(_normalizar_texto(kw) in t for kw in self.KW_COMPROVANTE) or any(kw in nome_lc for kw in ["comprovante", "residencia", "fatura"]):
                            tem_comprovante = True

                except Exception as e:
                    pendencias.append(f"O arquivo PDF '{path.name}' está corrompido ou é inválido ({e}).")
                    continue
            else:
                # Arquivos não-PDF (como imagens ou .docx avulsos)
                if any(kw in nome_lc for kw in ["ficha", "assinada"]):
                    tem_ficha = True
                if any(kw in nome_lc for kw in ["rg", "cnh", "identidade"]):
                    tem_doc_foto = True
                if any(kw in nome_lc for kw in ["comprovante", "residencia", "residência"]):
                    tem_comprovante = True

        if not tem_pdf_valido and not any(p.endswith(".pdf") for p in documentos_validos):
            pendencias.append("A documentação deve ser enviada preferencialmente em arquivo PDF.")

        if not tem_ficha:
            pendencias.append("Ficha Cadastral Assinada não identificada na documentação enviada.")
        if not tem_doc_foto:
            pendencias.append("Documento Oficial com Foto (RG/CPF/CNH) não identificado na documentação enviada.")
        if not tem_comprovante:
            pendencias.append("Comprovante de Residência não identificado na documentação enviada.")

        is_valido = len(pendencias) == 0

        print(f"[VALIDADOR DOCS (PyPDF)] Resultado da validação: Aprovado={is_valido}. Pendências: {pendencias}")

        return {
            "valido": is_valido,
            "pendencias": pendencias,
            "documentos_validos": documentos_validos
        }

def validar_documentos(caminho_anexos):
    validador = ValidadorDocumentos()
    res = validador.validar_documentos(caminho_anexos)
    return res.get("valido", False)
