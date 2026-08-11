import sys
from pathlib import Path

# Adiciona os caminhos necessários ao PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "source"))
sys.path.append(str(BASE_DIR / "resources"))

from source.orquestrador import main

if __name__ == "__main__":
    main()
