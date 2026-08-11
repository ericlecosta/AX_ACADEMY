"""
Módulo responsável pelo gerenciamento e organização física dos arquivos nas pastas do ERP e Google Drive.
"""
import os
import shutil
from pathlib import Path
from .gestor_drive import GestorDrive

class GestorArquivos:
    """
    Classe responsável por organizar e mover os arquivos recebidos
    nas pastas do ERP Simulado da Empresa Portal Fake (Local e Google Drive).
    """
    def __init__(self, base_erp_path: str = None):
        if base_erp_path:
            self.base_dir = Path(base_erp_path).resolve()
        else:
            # Aponta para ERP_Portal_Fake na raiz do repositório
            self.base_dir = (Path(__file__).resolve().parents[3] / "ERP_Portal_Fake").resolve()
        
        self.dir_downloads = self.base_dir / "Downloads"
        self.dir_ok = self.base_dir / "Documentos_OK"
        self.dir_pendentes = self.base_dir / "Documentos_Pendentes"
        self.dir_encaminhados = self.base_dir / "Encaminhados"

        # Conexão com Google Drive API v3
        self.gestor_drive = GestorDrive()

    def garantir_estrutura_pastas(self):
        """Cria as pastas do ERP caso ainda não existam localmente e no Google Drive."""
        for pasta in [self.dir_downloads, self.dir_ok, self.dir_pendentes, self.dir_encaminhados]:
            pasta.mkdir(parents=True, exist_ok=True)
        print(f"[GESTOR ARQUIVOS] Estrutura de pastas local garantida em: {self.base_dir}")

        # Cria a mesma estrutura no Google Drive
        self.gestor_drive.garantir_estrutura_pastas_drive()

    def mover_para_status(self, nome_arquivo: str, status_ok: bool) -> Path:
        """
        Move um arquivo da pasta Downloads para Documentos_OK ou
        Documentos_Pendentes localmente e no Google Drive.
        """
        origem = self.dir_downloads / nome_arquivo
        destino_pasta = self.dir_ok if status_ok else self.dir_pendentes
        destino = destino_pasta / nome_arquivo

        if not origem.exists():
            raise FileNotFoundError(f"Arquivo não encontrado em Downloads: {origem}")

        shutil.move(str(origem), str(destino))
        status_nome = "Documentos_OK" if status_ok else "Documentos_Pendentes"
        print(f"[GESTOR ARQUIVOS] Arquivo '{nome_arquivo}' movido localmente para '{status_nome}'.")

        # Repercute a movimentação no Google Drive
        self.gestor_drive.mover_arquivo(nome_arquivo, pasta_origem="Downloads", pasta_destino=status_nome, caminho_local=destino)

        return destino

    def mover_para_encaminhados(self, nome_arquivo: str) -> Path:
        """
        Move o arquivo validado da pasta Documentos_OK para Encaminhados após o
        envio ao setor localmente e no Google Drive.
        """
        origem = self.dir_ok / nome_arquivo
        destino = self.dir_encaminhados / nome_arquivo

        if not origem.exists():
            raise FileNotFoundError(f"Arquivo não encontrado em Documentos_OK: {origem}")

        shutil.move(str(origem), str(destino))
        print(f"[GESTOR ARQUIVOS] Arquivo '{nome_arquivo}' movido localmente para 'Encaminhados'.")

        # Repercute a movimentação no Google Drive
        self.gestor_drive.mover_arquivo(nome_arquivo, pasta_origem="Documentos_OK", pasta_destino="Encaminhados", caminho_local=destino)

        return destino