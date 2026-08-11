"""
Módulo responsável pela integração e ações de cadastro/atualização no ERP Portal Fake.
"""
from playwright.sync_api import Page

class PortalIntegracao:
    """
    Classe responsável por interagir via Playwright com o ERP Portal Fake
    para cadastrar e atualizar solicitações de clientes.
    """
    def __init__(self, page: Page = None):
        self.page = page

    def cadastrar_cliente(self, page: Page, dados_cliente: dict) -> bool:
        """
        Realiza o cadastro do cliente no Portal Fake ERP via Playwright.

        :param page: Objeto Page do Playwright.
        :param dados_cliente: Dicionário contendo os campos do cadastro.
        :return: True se o cadastro foi realizado com sucesso.
        """
        target_page = page or self.page
        if not target_page:
            raise ValueError("Uma página válida do Playwright deve ser fornecida.")

        print(f"[PORTAL INTEGRAÇÃO] Cadastrando cliente: {dados_cliente.get('nome', '')} {dados_cliente.get('sobrenome', '')} (CPF: {dados_cliente.get('cpf', '')})")

        try:
            # Aceita diálogos nativos se surgirem
            target_page.on("dialog", lambda dialog: dialog.accept())

            # Clica no botão 'Novo cadastro'
            target_page.click("#btnNovo")

            # Preenchimento dos campos do formulário
            target_page.fill("#f_nome", dados_cliente.get("nome", dados_cliente.get("Nome", "")))
            target_page.fill("#f_sobrenome", dados_cliente.get("sobrenome", dados_cliente.get("Sobrenome", "")))
            
            # Limpa formatação do CPF para manter apenas dígitos se necessário
            cpf_raw = str(dados_cliente.get("cpf", dados_cliente.get("CPF", "")))
            cpf_limpo = "".join(filter(str.isdigit, cpf_raw))
            if not cpf_limpo:
                cpf_limpo = "11122233344"
            target_page.fill("#f_cpf", cpf_limpo[:11])

            target_page.fill("#f_email", dados_cliente.get("email", dados_cliente.get("Email", "")))
            target_page.fill("#f_telefone", dados_cliente.get("telefone", dados_cliente.get("Telefone", "")))
            target_page.fill("#f_nascimento", dados_cliente.get("nascimento", dados_cliente.get("Nascimento", "1995-01-01")))
            target_page.fill("#f_endereco", dados_cliente.get("endereco", dados_cliente.get("Endereco", "")))
            target_page.fill("#f_observacao", dados_cliente.get("observacao", dados_cliente.get("Observacao", "Cadastrado via Automação de Atendimento")))

            status = dados_cliente.get("status", "ATIVO").upper()
            target_page.select_option("#f_status", status)

            # Clica em Salvar
            target_page.click("#btnSalvar")
            print(f"[PORTAL INTEGRAÇÃO] Cadastro de '{dados_cliente.get('nome', '')}' concluído com sucesso.")
            return True

        except Exception as e:
            print(f"[ERRO PORTAL INTEGRAÇÃO] Falha ao cadastrar cliente no portal: {e}")
            return False

    def atualizar_status_cadastro(self, page: Page, cpf: str, status: str) -> bool:
        """
        Atualiza o status de um cadastro existente no Portal Fake ERP.

        :param page: Objeto Page do Playwright.
        :param cpf: CPF do cliente a ser atualizado.
        :param status: Novo status ('ATIVO', 'PENDENTE', 'BLOQUEADO').
        :return: True se a atualização foi bem sucedida.
        """
        target_page = page or self.page
        if not target_page:
            raise ValueError("Uma página válida do Playwright deve ser fornecida.")

        print(f"[PORTAL INTEGRAÇÃO] Buscando CPF '{cpf}' para atualizar status para '{status}'...")

        try:
            cpf_limpo = "".join(filter(str.isdigit, str(cpf)))
            target_page.fill("#q", cpf_limpo)
            target_page.click("#btnBuscar")
            target_page.wait_for_timeout(300)

            # Verifica se há linhas de resultado
            rows = target_page.query_selector_all("#tbody tr")
            if not rows:
                print(f"[PORTAL INTEGRAÇÃO] Nenhum cadastro encontrado para o CPF '{cpf}'.")
                return False

            # Clica no botão de editar da primeira linha encontrada
            btn_editar = rows[0].query_selector(".btn-edit, button:has-text('Editar')")
            if btn_editar:
                btn_editar.click()
                target_page.select_option("#f_status", status.upper())
                target_page.click("#btnSalvar")
                print(f"[PORTAL INTEGRAÇÃO] Status do CPF '{cpf}' atualizado para '{status}'.")
                return True
            else:
                print(f"[PORTAL INTEGRAÇÃO] Botão de edição não localizado para a linha do CPF '{cpf}'.")
                return False

        except Exception as e:
            print(f"[ERRO PORTAL INTEGRAÇÃO] Falha ao atualizar status do cadastro: {e}")
            return False

def cadastrar_cliente(dados_cliente):
    pi = PortalIntegracao()
    return pi.cadastrar_cliente(None, dados_cliente)

def atualizar_status_cadastro(cpf, status):
    pi = PortalIntegracao()
    return pi.atualizar_status_cadastro(None, cpf, status)
