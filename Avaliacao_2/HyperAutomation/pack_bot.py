import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ZIP_FILE = BASE_DIR / "HyperAutomation.zip"

# Arquivos e pastas a incluir no pacote BotCity
INCLUDES = [
    "bot.py",
    "bot.yaml",
    "requirements.txt",
    "source",
    "resources"
]

# Padrões/pastas a ignorar
EXCLUDES = [
    "__pycache__",
    ".env",
    "browser_data",
    ".git",
    ".venv",
    ".DS_Store"
]

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDES or part.endswith(".pyc"):
            return True
    return False

def pack():
    print(f"Criando pacote para BotCity Maestro: {ZIP_FILE.name}...")
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as zipf:
        for item_name in INCLUDES:
            item_path = BASE_DIR / item_name
            if not item_path.exists():
                print(f"Aviso: {item_name} nao encontrado.")
                continue

            if item_path.is_file():
                if not should_exclude(item_path):
                    zipf.write(item_path, arcname=item_name)
                    print(f"  + Adicionado: {item_name}")
            elif item_path.is_dir():
                for file_path in item_path.rglob("*"):
                    if file_path.is_file() and not should_exclude(file_path):
                        arcname = file_path.relative_to(BASE_DIR)
                        zipf.write(file_path, arcname=arcname)
                        print(f"  + Adicionado: {arcname}")

    print(f"\nPacote BotCity gerado com sucesso: {ZIP_FILE}")

if __name__ == "__main__":
    pack()
