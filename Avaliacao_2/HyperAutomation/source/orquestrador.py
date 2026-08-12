import sys
import os
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from botcity.maestro import BotMaestroSDK, AutomationTaskFinishStatus

BASE_DIR = Path(__file__).resolve().parent
PATH_ROOT = BASE_DIR.parent
BROWSER_DATA_DIR = PATH_ROOT / "resources" / "browser_data"

sys.path.append(str(BASE_DIR))
sys.path.append(str(PATH_ROOT / "resources"))

from portal_bot import carregar_usuarios, preencher_portal_rapido, INDEX_HTML
from common.extracao import extrair_dados, extrair_todos_dados
from common.documento_email import criar_documento, enviar_email
from common.protocolo import gerar_protocolo_unico
from processo_atendimento.gestor_arquivos import GestorArquivos
from processo_atendimento.resposta_cliente import NotificadorCliente
from processo_atendimento.leitor_email import LeitorEmail
from processo_atendimento.validador_docs import ValidadorDocumentos
from processo_atendimento.portal_integracao import PortalIntegracao


def normalizar_dados_cliente(dados_cliente: dict) -> dict:
    """
    Normaliza o dicionário 'dados_cliente' retornado por LeitorEmail.ler_emails_pendentes().

    O formato das chaves varia conforme a origem:
    - E-mail real via IMAP (_processar_mensagem): chaves capitalizadas
      ("Nome", "Sobrenome", "CPF", "Email", "Telefone", "Endereco").
    - Retorno simulado (_gerar_retorno_simulado): chaves minúsculas
      ("nome", "sobrenome", "cpf", "email", "telefone", "endereco").

    NOTA: no caminho real (IMAP), _processar_mensagem hoje retorna Nome/Sobrenome/CPF
    FIXOS (placeholder) — apenas o e-mail do remetente é dinâmico. Para que nome e CPF
    corretos apareçam aqui, é necessário implementar a extração real desses dados a
    partir do PDF/anexo dentro de leitor_email.py (ex: lendo o PDF com pypdf, no mesmo
    espírito do que validador_docs.py já faz para localizar palavras-chave).
    """
    if not dados_cliente:
        return {}

    mapa = {
        "nome": ["nome", "Nome"],
        "sobrenome": ["sobrenome", "Sobrenome"],
        "cpf": ["cpf", "CPF"],
        "email": ["email", "Email", "E-mail"],
        "telefone": ["telefone", "Telefone"],
        "endereco": ["endereco", "Endereco", "Endereço"],
    }

    normalizado = {}
    for chave_padrao, variantes in mapa.items():
        for variante in variantes:
            valor = dados_cliente.get(variante)
            if valor:
                normalizado[chave_padrao] = valor
                break

    return normalizado


def main():
    # Inicializa conexão com o BotCity Maestro SDK (se executado via Runner)
    maestro = BotMaestroSDK.from_sys_args()

    parser = argparse.ArgumentParser(
        description="Orquestrador HyperAutomation - Processo 1 (Atendimento & Cadastro)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "modo_pos",
        nargs="?",
        default=None,
        help="Modo de execução posicional:\n"
             "  enviar_solicitacoes : Executa FASE 1 (geração e envio da ficha de assinatura)\n"
             "  processar_retornos  : Executa FASE 2 & 3 (leitura de e-mails de retorno e cadastro)\n"
             "  demo_completo       : Executa FASES 1, 2 e 3 integradas (demonstração completa)"
    )
    parser.add_argument(
        "-m", "--modo",
        choices=["enviar_solicitacoes", "processar_retornos", "demo_completo"],
        default=None,
        help="Modo de execução (sobrescreve o argumento posicional)"
    )
    parser.add_argument(
        "-r", "--row-index",
        type=int,
        default=2,
        help="Índice da linha do cliente no Portal Fake (padrão: 2, ignorado em processar_retornos)"
    )
    parser.add_argument(
        "-e", "--email-destino",
        type=str,
        default="2026500534@ifam.edu.br",
        help="E-mail de destino padrão para as solicitações"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Executar navegador em modo headless (sem interface gráfica)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Executar navegador com interface gráfica visível"
    )

    args, unknown = parser.parse_known_args()

    # Define valores via CLI
    modo = args.modo or args.modo_pos or "demo_completo"
    row_index = args.row_index
    email_destino = args.email_destino
    headless = args.headless

    task_id = None
    remetente = None
    senha = None

    if maestro.is_online:
        execution = maestro.get_execution()
        task_id = execution.task_id
        print(f"[BOTCITY] Maestro detectado! Task ID: {task_id}")

        params = execution.parameters or {}
        modo = params.get("modo", modo)
        try:
            row_index = int(params.get("row_index", row_index))
        except (ValueError, TypeError):
            pass
        email_destino = params.get("email_destino", email_destino)

        if "headless" in params:
            headless = str(params.get("headless")).lower() in ("true", "1", "yes")

        try:
            remetente = maestro.get_credential(label="GMAIL_CREDS", key="username")
            senha = maestro.get_credential(label="GMAIL_CREDS", key="password")
        except Exception:
            pass

    if headless is None:
        headless = True if (maestro and maestro.is_online) else False

    try:
        executar_orquestracao(
            modo=modo,
            row_index=row_index,
            email_destino=email_destino,
            headless=headless,
            maestro=maestro,
            task_id=task_id,
            remetente=remetente,
            senha=senha
        )

        if maestro.is_online and task_id:
            maestro.finish_task(
                task_id=task_id,
                status=AutomationTaskFinishStatus.SUCCESS,
                message=f"Orquestração (Modo: {modo}) concluída com sucesso no BotCity Maestro."
            )
    except Exception as e:
        print(f"[ERRO] Erro durante a execução do orquestrador: {e}")
        if maestro.is_online and task_id:
            maestro.finish_task(
                task_id=task_id,
                status=AutomationTaskFinishStatus.FAILED,
                message=f"Erro durante a execução: {e}"
            )
        raise e


def executar_orquestracao(modo="demo_completo", row_index=9, email_destino="carvalhosannyer@gmail.com",
                         headless=True, maestro=None, task_id=None, remetente=None, senha=None):
    """
    Executa a orquestração do Processo 1:

    - Nos modos "enviar_solicitacoes" e "demo_completo": abre o Portal Fake via Playwright,
      extrai os dados do cliente e executa a FASE 1 (geração da ficha + envio de e-mail).
    - No modo "processar_retornos": o navegador/Portal Fake NUNCA é aberto. Os dados do
      cliente vêm do e-mail de retorno (FASE 2), e o cadastro final no Portal (FASE 3,
      que dependeria do navegador) é PULADO — fica só registrado em log/arquivos.
    """
    print("=" * 75)
    print(f"INICIANDO ORQUESTRAÇÃO HYPERAUTOMATION - PROCESSO 1 (MODO: {modo.upper()})")
    print("=" * 75)

    somente_fase2 = modo == "processar_retornos"

    # 0. Inicialização dos Módulos
    print("\n[Etapa 0] Inicializando Módulos do Processo 1...")
    gestor_erp = GestorArquivos()
    gestor_erp.garantir_estrutura_pastas()

    notificador = NotificadorCliente()
    if remetente and senha:
        notificador.remetente = remetente
        notificador.senha = senha

    leitor_email = LeitorEmail(download_dir=gestor_erp.dir_downloads)
    validador = ValidadorDocumentos()
    portal_integracao = PortalIntegracao()

    screenshots_dir = PATH_ROOT / "resources" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # MODO "processar_retornos": roda a FASE 2 & 3 sem abrir navegador/Portal Fake
    # -----------------------------------------------------------------------
    if somente_fase2:
        _processar_retornos_sem_portal(
            gestor_erp=gestor_erp,
            notificador=notificador,
            leitor_email=leitor_email,
            validador=validador,
            email_destino=email_destino,
            maestro=maestro,
            task_id=task_id
        )
        print("\n" + "=" * 75)
        print("ORQUESTRAÇÃO DO PROCESSO 1 FINALIZADA COM SUCESSO!")
        print("=" * 75)
        return

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=headless
        )
        page = context.new_page()

        portal_url = f"file://{INDEX_HTML.resolve()}"

        # -----------------------------------------------------------------
        # PREPARAÇÃO E EXTRAÇÃO DE DADOS DO PORTAL FAKE
        # -----------------------------------------------------------------
        print(f"\n[Etapa 1] Conectando ao Portal Fake ERP: {portal_url}")
        page.goto(portal_url)

        usuarios_base = carregar_usuarios()
        preencher_portal_rapido(page, usuarios_base, qtd=10)

        print_portal = screenshots_dir / "01_portal_preenchido.png"
        page.screenshot(path=str(print_portal), full_page=True)
        print(f"  [SCREENSHOT] Salvo: {print_portal.name}")

        if maestro and maestro.is_online and task_id:
            try:
                maestro.post_artifact(task_id=task_id, artifact_name=print_portal.name, filepath=str(print_portal))
            except Exception:
                pass

        print(f"\n[Extração] Extraindo dados dinâmicos do cadastro na linha {row_index} do Portal Fake...")
        dados_extraidos = extrair_dados(page, row_index=row_index)

        nome = dados_extraidos.get("Nome", "Cliente")
        sobrenome = dados_extraidos.get("Sobrenome", "Solicitante")
        cpf = dados_extraidos.get("CPF", "11122233344")
        email_cliente = dados_extraidos.get("E-mail", email_destino)
        if not email_cliente or "@" not in email_cliente:
            email_cliente = email_destino

        telefone = dados_extraidos.get("Telefone", "(92) 99888-1122")
        endereco = dados_extraidos.get("Endereco", "Rua das Flores, 123 - Manaus/AM")

        cliente_dados = {
            "nome": nome,
            "sobrenome": sobrenome,
            "cpf": cpf,
            "email": email_cliente,
            "telefone": telefone,
            "endereco": endereco,
            "status": "PENDENTE"
        }
        protocolo = gerar_protocolo_unico()

        # =========================================================================
        # FASE 1: GERAÇÃO DA FICHA E DISPARO DO E-MAIL DE SOLICITAÇÃO DE ASSINATURA
        # =========================================================================
        if modo in ["enviar_solicitacoes", "demo_completo"]:
            print("\n" + "-" * 60)
            print(f"[FASE 1] GERAÇÃO E ENVIO DE FICHA PARA ASSINATURA ({nome} {sobrenome}) | Protocolo: {protocolo}")
            print("-" * 60)

            path_ficha_docx = criar_documento({
                "Nome": nome,
                "Sobrenome": sobrenome,
                "CPF": cpf,
                "Email": email_cliente,
                "Telefone": telefone,
                "Endereco": endereco,
                "Status": "AGUARDANDO ASSINATURA E DOCUMENTOS"
            })
            print(f"  [FASE 1] Ficha DOCX gerada a partir dos dados do portal: {Path(path_ficha_docx).name}")

            print(f"  [FASE 1] Enviando e-mail de solicitação de assinatura para {email_cliente}...")
            notificador.enviar_solicitacao_assinatura(
                email_destino=email_cliente,
                protocolo=protocolo,
                nome_cliente=f"{nome} {sobrenome}",
                caminho_ficha_docx=path_ficha_docx
            )
            print("  [FASE 1] Solicitação enviada! Cliente registrado no estado 'AGUARDANDO RETORNO'.")

            if modo == "enviar_solicitacoes":
                print("\n[FINALIZAÇÃO] Fase 1 concluída. O robô aguardará o envio do retorno do cliente.")
                context.close()
                return

            print("\n  [DEMO] Simulando recebimento do retorno do cliente...")
            time.sleep(2)

        # =========================================================================
        # FASE 2 & 3: MONITORAMENTO DA CAIXA DE RETORNO, VALIDAÇÃO E CADASTRO
        # (só executa aqui no modo demo_completo; processar_retornos usa
        #  _processar_retornos_sem_portal, sem navegador)
        # =========================================================================
        if modo == "demo_completo":
            print("\n" + "-" * 60)
            print(f"[FASE 2 & 3] MONITORAMENTO DO RETORNO, VALIDAÇÃO E CADASTRO")
            print("-" * 60)

            # Gera arquivo PDF simulado válido contendo os 3 documentos obrigatórios (apenas modo demo)
            if modo == "demo_completo":
                nome_limpo_pdf = f"Ficha_Assinada_e_Documentos_{nome}_{sobrenome}".replace(" ", "_")
                pdf_simulado = gestor_erp.dir_downloads / f"{nome_limpo_pdf}.pdf"
                if not pdf_simulado.exists() and not (gestor_erp.dir_ok / pdf_simulado.name).exists() and not (gestor_erp.dir_encaminhados / pdf_simulado.name).exists():
                    pdf_content = (
                        f"%PDF-1.4\n"
                        f"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
                        f"2 0 obj\n<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>\nendobj\n"
                        f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 9 0 R >> >> >>\nendobj\n"
                        f"4 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 7 0 R /Resources << /Font << /F1 9 0 R >> >> >>\nendobj\n"
                        f"5 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 8 0 R /Resources << /Font << /F1 9 0 R >> >> >>\nendobj\n"
                        f"6 0 obj\n<< /Length 120 >>\nstream\nBT\n/F1 12 Tf\n50 700 Td\n(Ficha Cadastral Assinada - Portal Fake Solucoes Digitais) Tj\n0 -20 Td\n(Cliente: {nome} {sobrenome} | CPF: {cpf}) Tj\nET\nendstream\nendobj\n"
                        f"7 0 obj\n<< /Length 120 >>\nstream\nBT\n/F1 12 Tf\n50 700 Td\n(Documento Oficial com Foto - RG / CPF / Identidade) Tj\n0 -20 Td\n(Registro Geral - SSP) Tj\nET\nendstream\nendobj\n"
                        f"8 0 obj\n<< /Length 120 >>\nstream\nBT\n/F1 12 Tf\n50 700 Td\n(Comprovante de Residencia - Conta de Luz / Agua / Fatura) Tj\n0 -20 Td\n(Endereco Residencial Confirmado) Tj\nET\nendstream\nendobj\n"
                        f"9 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
                        f"xref\n0 10\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000125 00000 n \n0000000244 00000 n \n0000000363 00000 n \n0000000482 00000 n \n0000000652 00000 n \n0000000812 00000 n \n0000000972 00000 n \ntrailer\n<< /Size 10 /Root 1 0 R >>\nstartxref\n1053\n%%EOF\n"
                    )
                    with open(pdf_simulado, "wb") as f:
                        f.write(pdf_content.encode('latin1'))

            print("  [FASE 2] Buscando novos e-mails de retorno não lidos (UNSEEN)...")
            permitir_sim = (modo == "demo_completo")
            solicitacoes_retornadas = leitor_email.ler_emails_pendentes(marcar_como_lido=True, permitir_simulacao=permitir_sim)

            if not solicitacoes_retornadas:
                print("  [FASE 2] Nenhum novo e-mail de retorno pendente localizado no momento.")
                context.close()
                return

            print(f"  [FASE 2] E-mails de retorno identificados para processar: {len(solicitacoes_retornadas)}")

            for idx, solic in enumerate(solicitacoes_retornadas, start=1):
                anexos = solic.get("anexos", [])

                print(f"\n  [Processando Retorno {idx}/{len(solicitacoes_retornadas)}] Cliente: {nome} {sobrenome} | Protocolo: #{protocolo}")
                print(f"    Anexos baixados: {[Path(a).name for a in anexos]}")

                # Validação documental
                res_validacao = validador.validar_documentos(anexos)

                if not res_validacao["valido"]:
                    print(f"    [VALIDAÇÃO] Documentação REPROVADA / PENDENTE para {nome} {sobrenome}.")
                    for a in anexos:
                        try:
                            gestor_erp.mover_para_status(Path(a).name, status_ok=False)
                        except Exception as e_mov:
                            print(f"    [GESTOR ARQUIVOS] Aviso: {e_mov}")

                    notificador.enviar_resposta(
                        email_destino=email_cliente,
                        protocolo=protocolo,
                        aprovado=False,
                        pendencias=res_validacao["pendencias"]
                    )
                else:
                    print(f"    [VALIDAÇÃO] Documentação e Ficha Assinada APROVADAS para {nome} {sobrenome}.")

                    # Move de Downloads para Documentos_OK
                    for a in anexos:
                        try:
                            gestor_erp.mover_para_status(Path(a).name, status_ok=True)
                        except Exception as e_mov:
                            print(f"    [GESTOR ARQUIVOS] Aviso: {e_mov}")

                    # Cadastro definitivo / Atualização de Status no Portal Fake via Playwright
                    cliente_dados["status"] = "ATIVO"
                    portal_integracao.cadastrar_cliente(page, cliente_dados)

                    # Move de Documentos_OK para Encaminhados
                    for a in anexos:
                        try:
                            gestor_erp.mover_para_encaminhados(Path(a).name)
                        except Exception as e_mov:
                            print(f"    [GESTOR ARQUIVOS] Aviso: {e_mov}")

                    # Envia e-mail final de confirmação em HTML
                    print(f"    [FASE 3] Enviando e-mail de CONFIRMAÇÃO DE CADASTRO para {email_cliente}...")
                    notificador.enviar_resposta(
                        email_destino=email_cliente,
                        protocolo=protocolo,
                        aprovado=True
                    )

            print_final = screenshots_dir / "02_extracao_dados.png"
            page.screenshot(path=str(print_final), full_page=True)
            print(f"    [SCREENSHOT] Salvo: {print_final.name}")

            if maestro and maestro.is_online and task_id:
                try:
                    maestro.post_artifact(task_id=task_id, artifact_name=print_final.name, filepath=str(print_final))
                except Exception:
                    pass

            context.close()

    print("\n" + "=" * 75)
    print("ORQUESTRAÇÃO DO PROCESSO 1 FINALIZADA COM SUCESSO!")
    print("=" * 75)


def _processar_retornos_sem_portal(gestor_erp, notificador, leitor_email, validador,
                                    email_destino, maestro=None, task_id=None):
    """
    Executa a FASE 2 & 3 (leitura de e-mails de retorno, validação documental e
    resposta ao cliente) SEM abrir o navegador/Portal Fake. Como consequência,
    o cadastro definitivo no Portal (portal_integracao.cadastrar_cliente) é
    PULADO nesse modo — o cliente aprovado fica registrado apenas via
    movimentação de arquivos (pasta 'Encaminhados') e e-mail de confirmação.
    """
    print("\n" + "-" * 60)
    print("[FASE 2 & 3] MONITORAMENTO DO RETORNO, VALIDAÇÃO E RESPOSTA (sem Portal Fake)")
    print("-" * 60)

    print("  [FASE 2] Buscando novos e-mails de retorno não lidos (UNSEEN)...")
    solicitacoes_retornadas = leitor_email.ler_emails_pendentes(marcar_como_lido=True, permitir_simulacao=False)

    if not solicitacoes_retornadas:
        print("  [FASE 2] Nenhum novo e-mail de retorno pendente localizado no momento.")
        return

    print(f"  [FASE 2] E-mails de retorno identificados para processar: {len(solicitacoes_retornadas)}")

    for idx, solic in enumerate(solicitacoes_retornadas, start=1):
        anexos = solic.get("anexos", [])

        # Dados do cliente extraídos do próprio e-mail/PDF de retorno
        dados_email = normalizar_dados_cliente(solic.get("dados_cliente", {}))
        nome = dados_email.get("nome", "Cliente")
        sobrenome = dados_email.get("sobrenome", "")
        cpf = dados_email.get("cpf", "")
        email_cliente = dados_email.get("email") or solic.get("remetente") or email_destino
        protocolo = solic.get("protocolo") or gerar_protocolo_unico()

        print(f"\n  [Processando Retorno {idx}/{len(solicitacoes_retornadas)}] Cliente: {nome} {sobrenome} | Protocolo: #{protocolo}")
        print(f"    Anexos baixados: {[Path(a).name for a in anexos]}")

        # Validação documental
        res_validacao = validador.validar_documentos(anexos)

        if not res_validacao["valido"]:
            print(f"    [VALIDAÇÃO] Documentação REPROVADA / PENDENTE para {nome} {sobrenome}.")
            for a in anexos:
                try:
                    gestor_erp.mover_para_status(Path(a).name, status_ok=False)
                except Exception as e_mov:
                    print(f"    [GESTOR ARQUIVOS] Aviso: {e_mov}")

            notificador.enviar_resposta(
                email_destino=email_cliente,
                protocolo=protocolo,
                aprovado=False,
                pendencias=res_validacao["pendencias"]
            )
        else:
            print(f"    [VALIDAÇÃO] Documentação e Ficha Assinada APROVADAS para {nome} {sobrenome}.")
            print("    [FASE 3] Cadastro no Portal Fake PULADO neste modo (navegador não é aberto em processar_retornos).")

            # Move de Downloads para Documentos_OK
            for a in anexos:
                try:
                    gestor_erp.mover_para_status(Path(a).name, status_ok=True)
                except Exception as e_mov:
                    print(f"    [GESTOR ARQUIVOS] Aviso: {e_mov}")

            # Move de Documentos_OK para Encaminhados
            for a in anexos:
                try:
                    gestor_erp.mover_para_encaminhados(Path(a).name)
                except Exception as e_mov:
                    print(f"    [GESTOR ARQUIVOS] Aviso: {e_mov}")

            # Envia e-mail final de confirmação
            print(f"    [FASE 3] Enviando e-mail de CONFIRMAÇÃO para {email_cliente}...")
            notificador.enviar_resposta(
                email_destino=email_cliente,
                protocolo=protocolo,
                aprovado=True
            )


if __name__ == "__main__":
    main()
