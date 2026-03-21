"""Utilitários compartilhados pelo pipeline de roteiros virais."""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Caminhos do projeto ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
TRANSCRIPTIONS_DIR = PROJECT_ROOT / "transcriptions"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"
TEMP_DIR = PROJECT_ROOT / "temp"


def setup_logging(name: str) -> logging.Logger:
    """Configura logger com saída em arquivo e console."""
    LOGS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Arquivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / f"{name}_{timestamp}.log", encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def load_env():
    """Carrega variáveis de ambiente do .env ou Streamlit Secrets."""
    load_dotenv(PROJECT_ROOT / ".env")

    # Tentar Streamlit Secrets (deploy na nuvem)
    if not os.getenv("OPENAI_API_KEY"):
        try:
            import streamlit as st
            key = st.secrets.get("OPENAI_API_KEY", "")
            if key:
                os.environ["OPENAI_API_KEY"] = key
        except Exception:
            pass

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY não encontrada no .env nem nos Streamlit Secrets")


def read_json(path: Path) -> dict | list:
    """Lê arquivo JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data, indent: int = 2):
    """Escreve dados em arquivo JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def read_client_brief() -> dict:
    """Lê o brief do cliente."""
    path = INPUTS_DIR / "client_brief.json"
    brief = read_json(path)
    required = ["client_name", "niche", "tone_of_voice", "formats"]
    missing = [k for k in required if not brief.get(k)]
    if missing:
        raise ValueError(f"Campos obrigatórios faltando no brief: {', '.join(missing)}")
    # Defaults para campos opcionais
    if not brief.get("avatar"):
        brief["avatar"] = f"Profissionais e decisores interessados em {brief['niche']}"
    if not brief.get("differentiator"):
        brief["differentiator"] = f"Expertise e autoridade em {brief['niche']}"
    return brief


def read_manus_research() -> dict:
    """Lê a pesquisa da Manus."""
    path = INPUTS_DIR / "manus_research.json"
    data = read_json(path)
    if not data.get("viral_videos"):
        raise ValueError("manus_research.json precisa ter pelo menos um vídeo em 'viral_videos'")
    return data
