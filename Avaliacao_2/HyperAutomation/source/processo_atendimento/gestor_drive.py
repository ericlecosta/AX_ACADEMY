"""
Módulo responsável pela integração e manipulação das pastas no Google Drive da conta remetente.
Gerencia a estrutura: ERP_Portal_Fake / (Downloads, Documentos_OK, Documentos_Pendentes, Encaminhados).
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class GestorDrive:
    """
    Classe responsável por autenticar na API do Google Drive (v3) e realizar a movimentação
    remota dos arquivos entre as pastas de status no Google Drive.
    """
    def __init__(self, credenciais_path: str = None, root_folder_id: str = None):
        self.service = None
        self.pastas_ids = {}
        self.base_folder_name = "ERP_Portal_Fake"
        self.subpastas_nomes = ["Downloads", "Documentos_OK", "Documentos_Pendentes", "Encaminhados"]
        self.root_folder_id = root_folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")

        # Busca caminho das credenciais (.json do Service Account ou OAuth)
        caminho_json = credenciais_path or os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if not caminho_json:
            # Tenta encontrar credentials.json na pasta source ou raiz
            base_dir = Path(__file__).resolve().parents[1]
            if (base_dir / "credentials.json").exists():
                caminho_json = str(base_dir / "credentials.json")
            elif (base_dir.parent / "credentials.json").exists():
                caminho_json = str(base_dir.parent / "credentials.json")

        self.caminho_json = caminho_json
        self._inicializar_servico()

    def _inicializar_servico(self):
        """Inicializa a conexão com o Google Drive API v3 suportando tanto Service Account quanto OAuth2."""
        if not self.caminho_json or not Path(self.caminho_json).exists():
            print("[GESTOR DRIVE] Aviso: Arquivo de credenciais do Google Drive não configurado ('credentials.json'). As movimentações serão salvas localmente.")
            return

        try:
            from google.oauth2 import service_account
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            SCOPES = ['https://www.googleapis.com/auth/drive']

            with open(self.caminho_json, 'r', encoding='utf-8') as f:
                cred_data = json.load(f)

            if cred_data.get("type") == "service_account":
                creds = service_account.Credentials.from_service_account_file(
                    self.caminho_json, scopes=SCOPES
                )
                print(f"[GESTOR DRIVE] Autenticado com sucesso via Service Account!")
            elif "installed" in cred_data or "web" in cred_data:
                token_path = Path(self.caminho_json).parent / "token.json"
                creds = None
                if token_path.exists():
                    try:
                        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                    except Exception:
                        creds = None

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        from google.auth.transport.requests import Request
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(self.caminho_json, SCOPES)
                        creds = flow.run_local_server(port=0)

                    with open(token_path, 'w', encoding='utf-8') as token:
                        token.write(creds.to_json())

                print(f"[GESTOR DRIVE] Autenticado com sucesso via OAuth 2.0 Client ID!")
            else:
                raise ValueError("O arquivo 'credentials.json' não possui formato válido (deve conter 'installed', 'web' ou 'type': 'service_account').")

            self.service = build('drive', 'v3', credentials=creds)
            print(f"[GESTOR DRIVE] Conexão com Google Drive API v3 estabelecida com sucesso!")
        except Exception as e:
            print(f"[GESTOR DRIVE] Não foi possível autenticar na API do Google Drive: {e}")

    def garantir_estrutura_pastas_drive(self) -> dict:
        """
        Cria ou mapeia a estrutura de pastas no Google Drive:
        ERP_Portal_Fake /
           ├── Downloads
           ├── Documentos_OK
           ├── Documentos_Pendentes
           └── Encaminhados
        """
        if not self.service:
            return {}

        try:
            # 1. Localiza ou usa a pasta raiz compartilhada ERP_Portal_Fake
            if self.root_folder_id:
                base_id = self.root_folder_id
                self.pastas_ids[self.base_folder_name] = base_id
                print(f"[GESTOR DRIVE] Usando ID configurado para a pasta raiz '{self.base_folder_name}': {base_id}")
            else:
                base_id = self._obter_ou_criar_pasta(self.base_folder_name, parent_id=None)
                self.pastas_ids[self.base_folder_name] = base_id

            # 2. Localiza ou cria as subpastas dentro da pasta raiz
            for sub in self.subpastas_nomes:
                sub_id = self._obter_ou_criar_pasta(sub, parent_id=base_id)
                self.pastas_ids[sub] = sub_id

            print(f"[GESTOR DRIVE] Estrutura de pastas no Google Drive pronta: {list(self.pastas_ids.keys())}")
            return self.pastas_ids
        except Exception as e:
            print(f"[GESTOR DRIVE] Erro ao criar estrutura de pastas no Drive: {e}")
            return {}

    def _obter_ou_criar_pasta(self, nome_pasta: str, parent_id: str = None) -> str:
        """Busca uma pasta por nome no Google Drive ou a cria se não existir."""
        query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{nome_pasta}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        response = self.service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, shared, owners)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = response.get('files', [])

        if files:
            # Se buscando a pasta raiz (parent_id is None) e houver múltiplos resultados,
            # dá preferência à pasta compartilhada pelo usuário humano
            if not parent_id and len(files) > 1:
                for f in files:
                    if f.get('shared'):
                        return f['id']
            return files[0]['id']

        # Se não existe, cria a pasta
        file_metadata = {
            'name': nome_pasta,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]

        folder = self.service.files().create(
            body=file_metadata, 
            fields='id',
            supportsAllDrives=True
        ).execute()
        return folder.get('id')

    def upload_arquivo(self, caminho_local: Path, nome_pasta_destino: str) -> str:
        """
        Realiza o upload de um arquivo local para uma pasta específica no Google Drive.
        """
        if not self.service:
            return None

        path_obj = Path(caminho_local)
        if not path_obj.exists():
            print(f"[GESTOR DRIVE] Arquivo local não encontrado para upload: {caminho_local}")
            return None

        if not self.pastas_ids:
            self.garantir_estrutura_pastas_drive()

        dest_folder_id = self.pastas_ids.get(nome_pasta_destino)
        if not dest_folder_id:
            dest_folder_id = self._obter_ou_criar_pasta(nome_pasta_destino, parent_id=self.pastas_ids.get(self.base_folder_name))
            self.pastas_ids[nome_pasta_destino] = dest_folder_id

        try:
            from googleapiclient.http import MediaFileUpload

            file_metadata = {
                'name': path_obj.name,
                'parents': [dest_folder_id]
            }
            media = MediaFileUpload(str(path_obj), resumable=True)
            file = self.service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields='id',
                supportsAllDrives=True
            ).execute()

            drive_file_id = file.get('id')
            print(f"[GESTOR DRIVE] Upload concluído para a pasta '{nome_pasta_destino}' no Google Drive (ID: {drive_file_id}).")
            return drive_file_id
        except Exception as e:
            print(f"[GESTOR DRIVE] Falha ao fazer upload de '{path_obj.name}' para o Drive: {e}")
            return None

    def mover_arquivo(self, nome_arquivo: str, pasta_origem: str, pasta_destino: str, caminho_local: Path = None) -> bool:
        """
        Move um arquivo existente de uma pasta de origem para uma pasta de destino no Google Drive.
        Caso o arquivo não exista no Drive, realiza o upload direto do arquivo local se caminho_local for fornecido.
        """
        if not self.service:
            return False

        if not self.pastas_ids:
            self.garantir_estrutura_pastas_drive()

        id_origem = self.pastas_ids.get(pasta_origem)
        id_destino = self.pastas_ids.get(pasta_destino)

        if not id_destino:
            id_destino = self._obter_ou_criar_pasta(pasta_destino, parent_id=self.pastas_ids.get(self.base_folder_name))
            self.pastas_ids[pasta_destino] = id_destino

        try:
            # Busca o arquivo na pasta de origem
            query = f"name = '{nome_arquivo}' and trashed = false"
            if id_origem:
                query += f" and '{id_origem}' in parents"

            results = self.service.files().list(
                q=query, 
                fields='files(id, name, parents)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = results.get('files', [])

            if not files:
                # Tenta buscar pelo nome do arquivo em qualquer pasta do ERP
                query_alt = f"name = '{nome_arquivo}' and trashed = false"
                results = self.service.files().list(
                    q=query_alt, 
                    fields='files(id, name, parents)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                files = results.get('files', [])

            if not files:
                print(f"[GESTOR DRIVE] Arquivo '{nome_arquivo}' não encontrado no Google Drive para mover.")
                if caminho_local and Path(caminho_local).exists():
                    print(f"[GESTOR DRIVE] Realizando upload de fallback para a pasta '{pasta_destino}'...")
                    return bool(self.upload_arquivo(caminho_local, nome_pasta_destino=pasta_destino))
                return False

            file_id = files[0]['id']
            previous_parents = ",".join(files[0].get('parents', []))

            # Altera os pais (parents) para mover de pasta no Drive
            self.service.files().update(
                fileId=file_id,
                addParents=id_destino,
                removeParents=previous_parents,
                fields='id, parents',
                supportsAllDrives=True
            ).execute()

            print(f"[GESTOR DRIVE] Arquivo '{nome_arquivo}' movido de '{pasta_origem}' para '{pasta_destino}' no Google Drive!")
            return True
        except Exception as e:
            print(f"[GESTOR DRIVE] Erro ao mover arquivo '{nome_arquivo}' no Google Drive: {e}")
            return False
