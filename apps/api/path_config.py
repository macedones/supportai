# ============================================================
# Faz o packages/core_py ficar importavel a partir da API.
#
# Estrutura do monorepo:
#   apps/api_py/      <- estamos aqui
#   packages/core_py/ <- db.py, embeddings.py, rag.py
#
# Equivalente ao "import { gerarEmbedding } from '../../packages/core/rag.js'"
# que o chat.js do Next.js NAO conseguia fazer (por isso duplicava
# tudo). Em Python isso e resolvido ajustando o sys.path uma unica
# vez, aqui, antes de qualquer outro import do projeto.
# ============================================================

import sys
from pathlib import Path

CORE_PY_PATH = Path(__file__).resolve().parent.parent.parent / "packages" / "core"

if str(CORE_PY_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PY_PATH))
