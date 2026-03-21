"""
Pipeline completo — roda todas as etapas em sequência.

Uso:
  python run_pipeline.py                  → roda etapas 1-4 (transcrição ao PDF)
  python run_pipeline.py --from 2         → começa da etapa 2 (análise)
  python run_pipeline.py --from 0         → começa da pesquisa (gera prompt Manus)
  python run_pipeline.py --only 4         → roda apenas o PDF
  python run_pipeline.py --clean          → limpa dados anteriores antes de rodar
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Caminhos
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
PYTHON = sys.executable

STEPS = {
    0: ("00_research.py", "Pesquisa (prompt Manus)"),
    1: ("01_transcribe.py", "Transcrição de vídeos"),
    2: ("02_analyze.py", "Análise de padrões virais"),
    3: ("03_generate_scripts.py", "Geração dos 30 roteiros"),
    4: ("04_generate_pdf.py", "Geração do PDF"),
}


def clean_data():
    """Limpa dados de execuções anteriores."""
    dirs_to_clean = ["transcriptions", "analysis", "scripts", "output", "temp", "logs"]
    for d in dirs_to_clean:
        path = PROJECT_ROOT / d
        if path.exists():
            for f in path.iterdir():
                if f.is_file():
                    f.unlink()
    print("[CLEAN] Dados anteriores removidos.\n")


def run_step(step_num: int) -> bool:
    """Executa uma etapa do pipeline."""
    script_name, description = STEPS[step_num]
    script_path = SRC_DIR / script_name

    if not script_path.exists():
        print(f"[ERRO] Script não encontrado: {script_path}")
        return False

    print(f"\n{'=' * 60}")
    print(f"  ETAPA {step_num} — {description}")
    print(f"{'=' * 60}\n")

    # Etapa 0 (pesquisa) é especial — só gera o prompt e para
    if step_num == 0:
        result = subprocess.run(
            [PYTHON, str(script_path), "prompt"],
            cwd=str(SRC_DIR),
        )
        if result.returncode == 0:
            print("\n[INFO] Prompt gerado. Cole na Manus e importe a resposta com:")
            print(f"       python {script_name} importar resposta_manus.txt")
            print("[INFO] Depois rode: python run_pipeline.py --from 1")
        return result.returncode == 0

    start = time.time()

    result = subprocess.run(
        [PYTHON, str(script_path)],
        cwd=str(SRC_DIR),
    )

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    if result.returncode == 0:
        print(f"\n[OK] Etapa {step_num} concluída em {minutes}m{seconds}s")
        return True
    else:
        print(f"\n[ERRO] Etapa {step_num} falhou (código {result.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pipeline de Roteiros Virais")
    parser.add_argument("--from", dest="start", type=int, default=1,
                        help="Etapa inicial (0-4, padrão: 1)")
    parser.add_argument("--to", dest="end", type=int, default=4,
                        help="Etapa final (0-4, padrão: 4)")
    parser.add_argument("--only", type=int, default=None,
                        help="Rodar apenas esta etapa")
    parser.add_argument("--clean", action="store_true",
                        help="Limpar dados anteriores antes de rodar")
    args = parser.parse_args()

    print("""
    ╔══════════════════════════════════════════╗
    ║   PIPELINE DE ROTEIROS VIRAIS — v1.0     ║
    ╚══════════════════════════════════════════╝
    """)

    if args.clean:
        clean_data()

    if args.only is not None:
        steps_to_run = [args.only]
    else:
        steps_to_run = list(range(args.start, args.end + 1))

    valid_steps = [s for s in steps_to_run if s in STEPS]
    if not valid_steps:
        print("[ERRO] Nenhuma etapa válida selecionada (0-4)")
        sys.exit(1)

    print(f"Etapas: {' → '.join(STEPS[s][1] for s in valid_steps)}\n")

    total_start = time.time()
    failed = False

    for step in valid_steps:
        ok = run_step(step)
        if not ok:
            failed = True
            if step == 0:
                # Etapa 0 sempre para — é interativa
                break
            print(f"\n[AVISO] Etapa {step} falhou. Continuando...\n")

    total_elapsed = time.time() - total_start
    total_min = int(total_elapsed // 60)
    total_sec = int(total_elapsed % 60)

    print(f"\n{'=' * 60}")
    if not failed:
        print(f"  PIPELINE CONCLUÍDO — {total_min}m{total_sec}s")
        pdf_dir = PROJECT_ROOT / "output"
        pdfs = list(pdf_dir.glob("*.pdf"))
        if pdfs:
            print(f"  PDF: {pdfs[-1]}")
    else:
        print(f"  PIPELINE CONCLUÍDO COM AVISOS — {total_min}m{total_sec}s")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
