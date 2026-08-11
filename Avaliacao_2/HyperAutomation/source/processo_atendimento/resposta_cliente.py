"""
Módulo responsável por enviar respostas por e-mail informando o status ao cliente.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from dotenv import load_dotenv
from common.protocolo import gerar_protocolo_unico

load_dotenv()

class NotificadorCliente:
    """
    Classe responsável por enviar e-mails de solicitação inicial e resposta automática aos clientes.
    """
    def __init__(self):
        smtp_server_env = os.getenv("SMTP_SERVER")
        self.smtp_server = smtp_server_env if smtp_server_env else "smtp.gmail.com"

        smtp_port_env = os.getenv("SMTP_PORT")
        if smtp_port_env and smtp_port_env.strip().isdigit():
            self.smtp_port = int(smtp_port_env.strip())
        else:
            self.smtp_port = 587

        self.remetente = os.getenv("EMAIL_REMETENTE")
        self.senha = os.getenv("EMAIL_SENHA")

    def enviar_solicitacao_assinatura(self, email_destino: str, protocolo: str, nome_cliente: str, caminho_ficha_docx: str) -> bool:
        """
        Envia o e-mail inicial contendo a Ficha de Dados para o cliente assinar
        e instrui o envio de retorno com a ficha assinada e documentos em um único PDF.
        """
        if not self.remetente or not self.senha:
            print(f"[AVISO NOTIFICADOR] Credenciais SMTP não configuradas. Simulado envio da Ficha para Assinatura (Protocolo: #{protocolo}) -> {email_destino}")
            return True

        msg = MIMEMultipart()
        msg["From"] = self.remetente
        msg["To"] = email_destino
        msg["Subject"] = f"Ação Necessária: Assinatura de Ficha Cadastral - Protocolo #{protocolo}"

        corpo_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="background-color: #f4f6f8; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #1976d2; margin-top: 0;">Solicitação de Atendimento - Assinatura Pendente</h2>
                    <p>Olá, <strong>{nome_cliente}</strong>,</p>
                    <p>Sua solicitação no Setor de Atendimento da <strong>Empresa Portal Fake</strong> foi iniciada sob o protocolo <strong>#{protocolo}</strong>.</p>
                    <p>Geramos em anexo a sua <strong>Ficha Cadastral para Assinatura</strong>.</p>
                    
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #1976d2; margin: 15px 0;">
                        <h4 style="margin-top: 0; color: #1976d2;">📋 Instruções para Retorno:</h4>
                        <ol>
                            <li>Baixe e imprima ou assine digitalmente a ficha cadastral em anexo.</li>
                            <li>Reúna a <strong>Ficha Assinada</strong> juntamente com seus <strong>Documentos Pessoais (RG/CPF)</strong> e <strong>Comprovante de Residência</strong>.</li>
                            <li>Digitalize ou unifique todos os documentos em um <strong>ÚNICO arquivo PDF</strong>.</li>
                            <li>Responda a este e-mail anexando o PDF unificado.</li>
                        </ol>
                    </div>
                    <br>
                    <p style="font-size: 12px; color: #777;">Atenciosamente,<br><strong>Equipe de Atendimento Automatizado - Hyperautomation</strong></p>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(corpo_html, "html"))

        # Anexa a Ficha .docx para assinatura
        if caminho_ficha_docx and Path(caminho_ficha_docx).exists():
            path_file = Path(caminho_ficha_docx)
            with open(path_file, "rb") as f:
                part = MIMEApplication(f.read(), Name=path_file.name)
                part['Content-Disposition'] = f'attachment; filename="{path_file.name}"'
                msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.remetente, self.senha)
                server.send_message(msg)
                print(f"[NOTIFICADOR] E-mail de solicitação de assinatura enviado para {email_destino} (Protocolo: #{protocolo}).")
                return True
        except Exception as e:
            print(f"[AVISO NOTIFICADOR] Falha no envio do e-mail inicial para {email_destino}: {e}")
            return False

    def enviar_resposta(self, email_destino: str, protocolo: str, aprovado: bool, pendencias: list = None) -> bool:
        """
        Envia e-mail de notificação de resultado da validação (Aprovado ou Pendente).
        """
        if not self.remetente or not self.senha:
            print(f"[AVISO NOTIFICADOR] Credenciais SMTP não configuradas. Simulado envio de notificação final para: {email_destino} (Aprovado: {aprovado})")
            return True

        msg = MIMEMultipart("alternative")
        msg["From"] = self.remetente
        msg["To"] = email_destino

        if aprovado:
            msg["Subject"] = f"Cadastro Concluído e Aprovado - Protocolo #{protocolo}"
            corpo_html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <div style="background-color: #f4f6f8; padding: 20px; border-radius: 8px;">
                        <h2 style="color: #2e7d32; margin-top: 0;">Solicitação Aprovada e Cadastrada!</h2>
                        <p>Olá,</p>
                        <p>Recebemos o seu retorno referente ao protocolo <strong>#{protocolo}</strong> com a <strong>Ficha Assinada</strong> e documentos unificados.</p>
                        <p>Toda a documentação foi devidamente validada e o seu cadastro foi efetuado no sistema ERP da <strong>Empresa Portal Fake</strong>.</p>
                        <br>
                        <p style="font-size: 12px; color: #777;">Atenciosamente,<br><strong>Equipe de Atendimento Automatizado - Hyperautomation</strong></p>
                    </div>
                </body>
            </html>
            """
        else:
            msg["Subject"] = f"Pendência no Retorno de Documentos - Protocolo #{protocolo}"
            itens_pendentes = "".join([f"<li style='margin-bottom: 5px;'>{item}</li>" for item in (pendencias or ["Documentação incompleta ou não assinada"])])
            corpo_html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <div style="background-color: #fff4f4; padding: 20px; border-radius: 8px; border: 1px solid #ffcdd2;">
                        <h2 style="color: #c62828; margin-top: 0;">Inconsistência na Documentação Enviada</h2>
                        <p>Olá,</p>
                        <p>Analisamos o arquivo retornado para o protocolo <strong>#{protocolo}</strong> e identificamos as seguintes pendências:</p>
                        <ul style="color: #b71c1c;">
                            {itens_pendentes}
                        </ul>
                        <p>Por favor, responda a este e-mail anexando a Ficha devidamente Assinada e os documentos em um único PDF corrigido.</p>
                        <br>
                        <p style="font-size: 12px; color: #777;">Atenciosamente,<br><strong>Equipe de Atendimento Automatizado - Hyperautomation</strong></p>
                    </div>
                </body>
            </html>
            """

        msg.attach(MIMEText(corpo_html, "html"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.remetente, self.senha)
                server.send_message(msg)
                print(f"[NOTIFICADOR] E-mail de resposta enviado para {email_destino} (Protocolo: #{protocolo}).")
                return True
        except Exception as e:
            print(f"[AVISO NOTIFICADOR] Falha ao enviar e-mail para {email_destino}: {e}")
            return False

def enviar_resposta_cliente(email_destino, aprovado=True, mensagem="", protocolo=None):
    notificador = NotificadorCliente()
    prot = protocolo if protocolo else gerar_protocolo_unico()
    return notificador.enviar_resposta(email_destino, protocolo=prot, aprovado=aprovado, pendencias=[mensagem] if mensagem else None)