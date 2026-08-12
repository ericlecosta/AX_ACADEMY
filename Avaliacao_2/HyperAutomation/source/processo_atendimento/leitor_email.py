"""
Módulo responsável pelo monitoramento da caixa de entrada, leitura de e-mails de retorno de clientes e download dos PDFs unificados.
"""
import os
import re
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from dotenv import load_dotenv
from pypdf import PdfReader
from common.protocolo import gerar_protocolo_unico

load_dotenv()

class LeitorEmail:
    """
    Classe responsável por conectar à caixa de entrada (IMAP) e monitorar e-mails de retorno
    enviados pelos clientes contendo a Ficha Assinada e os Documentos em um único PDF.
    Garante que e-mails já lidos/processados não sejam analisados duplamente (Flag \\Seen).
    """
    def __init__(self, download_dir: Path = None):
        self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.email_user = os.getenv("EMAIL_REMETENTE")
        self.email_pass = os.getenv("EMAIL_SENHA")

        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = (Path(__file__).resolve().parents[3] / "ERP_Portal_Fake" / "Downloads").resolve()

        self.download_dir.mkdir(parents=True, exist_ok=True)
        from .gestor_drive import GestorDrive
        self.gestor_drive = GestorDrive()

    def ler_emails_pendentes(self, marcar_como_lido: bool = True, permitir_simulacao: bool = False) -> list:
        """
        Monitora a caixa de entrada exclusivamente por e-mails NÃO LIDOS (UNSEEN) contendo respostas de clientes.
        :param marcar_como_lido: Se True, aplica a flag \\Seen no servidor IMAP para não ler 2 vezes.
        :param permitir_simulacao: Se True, injeta dados simulados para apresentações de teste caso o IMAP falhe.
        """
        solicitacoes = []

        if self.email_user and self.email_pass and self.imap_server:
            try:
                print(f"[LEITOR EMAIL] Conectando ao servidor IMAP {self.imap_server} para buscar e-mails não lidos (UNSEEN)...")
                mail = imaplib.IMAP4_SSL(self.imap_server)
                mail.login(str(self.email_user), str(self.email_pass))
                mail.select("inbox")

                # Busca estrita por e-mails NÃO LIDOS (UNSEEN) que contenham "Assinatura" ou "Retorno" no assunto
                status, messages = mail.search(None, '(UNSEEN SUBJECT "Assinatura")')
                email_ids = messages[0].split()

                if not email_ids:
                    # Busca alternativa por termo de retorno
                    status, messages = mail.search(None, '(UNSEEN SUBJECT "Ficha")')
                    email_ids = messages[0].split()

                print(f"[LEITOR EMAIL] Encontrados {len(email_ids)} novos e-mails não lidos de retorno de clientes.")

                for mail_id in email_ids:
                    _, msg_data = mail.fetch(mail_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            solicitacao = self._processar_mensagem(msg)
                            if solicitacao:
                                solicitacoes.append(solicitacao)

                            # Marca o e-mail como LIDO (\Seen) no servidor
                            if marcar_como_lido:
                                mail.store(mail_id, '+FLAGS', '\\Seen')
                                print(f"[LEITOR EMAIL] E-mail ID {mail_id.decode()} marcado como LIDO (\\Seen) no servidor.")

                mail.close()
                mail.logout()
                # Retorna os e-mails reais encontrados (se não houver nenhum, retorna lista vazia)
                return solicitacoes

            except Exception as e:
                print(f"[AVISO LEITOR EMAIL] Não foi possível conectar via IMAP ({e}).")

        # Se simulação for explicitamente permitida (modo demo), gera o retorno simulado
        if permitir_simulacao:
            print("[LEITOR EMAIL] Modo demonstração ativo: gerando retorno simulado de teste...")
            return self._gerar_retorno_simulado()

        print("[LEITOR EMAIL] Nenhum novo e-mail não lido localizado na caixa de entrada.")
        return []

    def _processar_mensagem(self, msg) -> dict:
        """Processa a mensagem individual do e-mail retornado pelo cliente e baixa anexos."""
        remetente = msg.get("From", "cliente@exemplo.com")
        assunto = msg.get("Subject", "Retorno de Documentos")

        anexos_baixados = self.baixar_anexos(msg)

        dados_ficha = self._extrair_dados_ficha_pdf(anexos_baixados)

        return {
            "remetente": remetente,
            "assunto": assunto,
            "anexos": anexos_baixados,
            "dados_cliente": {
                "Nome": dados_ficha.get("nome", "Cliente"),
                "Sobrenome": dados_ficha.get("sobrenome", "Retorno"),
                "CPF": dados_ficha.get("cpf", "11122233344"),
                "Email": dados_ficha.get("email") or remetente,
                "Telefone": dados_ficha.get("telefone", "(92) 99888-1122"),
                "Nascimento": dados_ficha.get("nascimento", ""),
                "Endereco": dados_ficha.get("endereco", "Rua das Flores, 123 - Manaus/AM")
            }
        }

    def _extrair_dados_ficha_pdf(self, anexos: list) -> dict:
        """
        Extrai os dados da Ficha de Cadastro (nome, sobrenome, CPF, e-mail, telefone,
        data de nascimento e endereço) a partir do texto do PDF retornado pelo cliente.

        Espera o mesmo formato numerado gerado por common/documento_email.py:
            1. Nome: ...
            2. Sobrenome: ...
            3. CPF: ...
            4. E-mail: ...
            5. Telefone: ...
            6. Data de Nascimento: ...
            7. Endereço: ...

        Percorre os PDFs anexados até encontrar um cujo texto contenha, no mínimo,
        Nome e CPF preenchidos. Se o PDF for uma imagem escaneada (sem texto
        extraível), retorna vazio — nesse caso seria necessário OCR (não implementado).
        """
        campos = {
            "nome": r"1\.\s*Nome:\s*(.+)",
            "sobrenome": r"2\.\s*Sobrenome:\s*(.+)",
            "cpf": r"3\.\s*CPF:\s*(.+)",
            "email": r"4\.\s*E-?mail:\s*(.+)",
            "telefone": r"5\.\s*Telefone:\s*(.+)",
            "nascimento": r"6\.\s*Data de Nascimento:\s*(.+)",
            "endereco": r"7\.\s*Endere[cç]o:\s*(.+)",
        }

        for anexo in anexos:
            caminho = Path(anexo)
            if caminho.suffix.lower() != ".pdf":
                continue

            try:
                texto = ""
                reader = PdfReader(caminho)
                for pagina in reader.pages:
                    texto += (pagina.extract_text() or "") + "\n"

                dados = {}
                for chave, padrao in campos.items():
                    match = re.search(padrao, texto, re.IGNORECASE)
                    if not match:
                        continue
                    valor = match.group(1).strip()
                    # Evita colar o próximo campo numerado na mesma captura
                    valor = re.split(r"\s{2,}\d\.\s", valor)[0].strip()
                    if valor:
                        dados[chave] = valor

                if dados.get("nome") and dados.get("cpf"):
                    print(f"[LEITOR EMAIL] Dados da Ficha extraídos de '{caminho.name}': "
                          f"{dados.get('nome')} {dados.get('sobrenome', '')} | CPF: {dados.get('cpf')}")
                    return dados

            except Exception as e:
                print(f"[LEITOR EMAIL] Aviso: não foi possível ler '{caminho.name}' em busca da Ficha de Cadastro: {e}")

        print("[LEITOR EMAIL] Aviso: não foi possível localizar os dados da Ficha de Cadastro nos anexos "
              "(PDF sem texto extraível ou fora do formato esperado). Usando dados de fallback.")
        return {}

    def baixar_anexos(self, mensagem) -> list:
        """
        Extrai e salva os PDFs baixados da mensagem de e-mail na pasta ERP_Portal_Fake/Downloads.
        """
        anexos = []
        if not hasattr(mensagem, "walk"):
            return anexos

        for part in mensagem.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get("Content-Disposition") is None:
                continue

            filename = part.get_filename()
            if filename:
                filename = decode_header(filename)[0][0]
                if isinstance(filename, bytes):
                    filename = filename.decode()

                caminho_salvo = self.download_dir / filename
                with open(caminho_salvo, "wb") as f:
                    f.write(part.get_payload(decode=True))

                anexos.append(caminho_salvo)
                print(f"[LEITOR EMAIL] Novo PDF de retorno baixado para Downloads: {caminho_salvo.name}")
                # Sincroniza o upload com o Google Drive
                self.gestor_drive.upload_arquivo(caminho_salvo, nome_pasta_destino="Downloads")

        return anexos

    def _gerar_retorno_simulado(self) -> list:
        """
        Gera retorno simulado em ERP_Portal_Fake/Downloads caso haja arquivo pendente de processamento.
        """
        pdf_unificado = self.download_dir / "Ficha_Assinada_e_Documentos_Ana_Silva.pdf"
        protocolo_unico = gerar_protocolo_unico()

        if pdf_unificado.exists():
            print("[LEITOR EMAIL] Identificado 1 novo retorno pendente em Downloads...")
            return [{
                "id": f"RET-{protocolo_unico}",
                "protocolo": protocolo_unico,
                "remetente": "ana.silva@exemplo.com",
                "assunto": f"RES: Assinatura de Ficha Cadastral - Protocolo #{protocolo_unico}",
                "dados_cliente": {
                    "nome": "Ana",
                    "sobrenome": "Silva",
                    "cpf": "11122233344",
                    "email": "ana.silva@exemplo.com",
                    "telefone": "(92) 99888-1122",
                    "nascimento": "1992-05-15",
                    "endereco": "Rua das Flores, 123 - Manaus/AM",
                    "observacao": "Ficha assinada e documentos anexados em PDF único."
                },
                "anexos": [str(pdf_unificado)]
            }]

        return []

def ler_emails_pendentes():
    leitor = LeitorEmail()
    return leitor.ler_emails_pendentes()

def baixar_anexos(mensagem):
    leitor = LeitorEmail()
    return leitor.baixar_anexos(mensagem)
