"""
Frontend do Sistema de Roteiros Virais — Streamlit.
Uso: streamlit run app.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

# ── Caminhos ─────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
TRANSCRIPTIONS_DIR = PROJECT_ROOT / "transcriptions"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUT_DIR = PROJECT_ROOT / "output"
PYTHON = sys.executable

# ── Configuração da página ───────────────────────────────────────────
st.set_page_config(
    page_title="Roteiros Virais",
    page_icon="▶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS customizado ──────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        font-weight: 600;
    }
    .status-ok { color: #2e7d32; font-weight: 600; }
    .status-err { color: #c62828; font-weight: 600; }
    .status-wait { color: #888; }
    .metric-box {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        border: 1px solid #e0e0e0;
    }
    .metric-num {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
    }
    .metric-label {
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

# ── Constantes ───────────────────────────────────────────────────────
TONES = [
    "Direto, executivo e explicativo",
    "Leve e humorístico",
    "Provocador e polêmico",
    "Educativo e didático",
    "Inspiracional e motivacional",
    "Técnico e especialista",
]

FORMATS = [
    "Reels/TikTok curtos",
    "YouTube Shorts",
    "Stories",
    "vídeos médios",
]

STEPS_INFO = {
    1: {"script": "01_transcribe.py", "name": "Transcrição", "icon": "🎙"},
    2: {"script": "02_analyze.py", "name": "Análise", "icon": "🔍"},
    3: {"script": "03_generate_scripts.py", "name": "Roteiros", "icon": "✏"},
    4: {"script": "04_generate_pdf.py", "name": "PDF", "icon": "📄"},
}


# ── Funções auxiliares ───────────────────────────────────────────────
def read_json_safe(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_brief() -> dict:
    data = read_json_safe(INPUTS_DIR / "client_brief.json")
    if data:
        return data
    return {
        "client_name": "",
        "niche": "",
        "tone_of_voice": TONES[0],
        "formats": ["Reels/TikTok curtos"],
        "avatar": "",
        "differentiator": "",
    }


def save_brief(name, niche, tone, formats):
    brief = {
        "client_name": name,
        "niche": niche,
        "tone_of_voice": tone,
        "formats": formats,
        "avatar": f"Profissionais e decisores interessados em {niche}",
        "differentiator": f"Expertise e autoridade em {niche}",
    }
    write_json_file(INPUTS_DIR / "client_brief.json", brief)
    return brief


def count_files(directory: Path, ext: str = "*.json") -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob(ext)))


def run_script(script_name: str, status_container) -> tuple[bool, str]:
    """Roda um script Python e captura a saída."""
    script_path = SRC_DIR / script_name
    output_lines = []

    process = subprocess.Popen(
        [PYTHON, str(script_path)],
        cwd=str(SRC_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    for line in process.stdout:
        output_lines.append(line.rstrip())
        # Mostrar últimas linhas no status
        recent = "\n".join(output_lines[-8:])
        status_container.code(recent, language=None)

    process.wait()
    full_output = "\n".join(output_lines)
    return process.returncode == 0, full_output


def generate_manus_prompt(niche: str, client_name: str, tone: str) -> str:
    """Gera o prompt para a Manus."""
    return f"""Preciso que você pesquise os perfis mais virais no nicho de "{niche}" nas redes sociais (Instagram, TikTok e YouTube).

TAREFA:
1. Encontre os 10 perfis mais relevantes e com maior engajamento neste nicho.
2. Para cada perfil, liste os 2-3 reels/vídeos/shorts com MAIOR número de views.
3. Priorize vídeos CURTOS (reels, shorts, TikToks) — não vídeos longos acima de 5 minutos.
4. Apenas vídeos com ÁUDIO FALADO (não apenas música ou texto na tela).

FORMATO DE RESPOSTA — retorne EXATAMENTE neste formato JSON (sem texto antes ou depois):

```json
{{
  "profiles": [
    {{
      "name": "Nome do criador",
      "handle": "@handle",
      "platform": "instagram",
      "followers": 500000,
      "avg_engagement": 5.2
    }}
  ],
  "viral_videos": [
    {{
      "url": "https://www.instagram.com/reel/XXXXX/",
      "profile": "@handle",
      "platform": "instagram",
      "views": 2500000,
      "likes": 180000,
      "comments": 4500,
      "description": "Descrição curta do conteúdo do vídeo"
    }}
  ]
}}
```

REGRAS:
- URLs devem ser links DIRETOS para o vídeo/reel (não para o perfil).
- Para Instagram: https://www.instagram.com/reel/CODIGO/
- Para YouTube: https://www.youtube.com/watch?v=CODIGO ou /shorts/CODIGO
- Para TikTok: https://www.tiktok.com/@handle/video/CODIGO
- Inclua métricas reais (views, likes, comentários).
- Mínimo de 15 vídeos, máximo de 25.
- O JSON deve ser válido e parseável diretamente.

NICHO: {niche}
CONTEXTO: Cliente: {client_name}. Tom de voz: {tone}."""


def parse_manus_response(text: str) -> dict | None:
    """Parseia resposta da Manus (JSON ou tabela markdown)."""
    import re

    # Tentar JSON direto
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Extrair bloco ```json```
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Extrair JSON de texto
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Parsear tabela markdown
    profiles = {}
    videos = []
    lines = [l.strip() for l in text.split("\n") if "|" in l and "---" not in l]

    if len(lines) < 2:
        return None

    for line in lines[1:]:
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 4:
            continue

        profile_name = cols[0].strip()
        urls_col1 = re.findall(r'\(?(https?://[^\s\)]+)\)?', cols[1])
        urls_col3 = re.findall(r'\(?(https?://[^\s\)]+)\)?', cols[3])

        profile_url = urls_col1[0] if urls_col1 else ""
        video_url = urls_col3[0] if urls_col3 else ""
        video_desc = re.sub(r'\[.*?\]\(.*?\)', '', cols[2]).strip().strip('"')

        platform = "instagram"
        if "youtube.com" in video_url:
            platform = "youtube"
        elif "tiktok.com" in video_url:
            platform = "tiktok"

        handle = ""
        h = re.search(r'instagram\.com/([^/?]+)', profile_url)
        if h:
            handle = f"@{h.group(1)}"

        if profile_name and profile_name not in profiles:
            profiles[profile_name] = {
                "name": profile_name, "handle": handle,
                "platform": platform, "followers": 0, "avg_engagement": 0,
            }

        if video_url and ("/reel/" in video_url or "/p/" in video_url or
                          "watch?v=" in video_url or "/shorts/" in video_url or
                          "/video/" in video_url):
            videos.append({
                "url": video_url, "profile": handle or profile_name,
                "platform": platform, "views": 0, "likes": 0,
                "comments": 0, "description": video_desc,
            })

    if not videos:
        return None

    return {"profiles": list(profiles.values()), "viral_videos": videos}


# ══════════════════════════════════════════════════════════════════════
# SIDEBAR — Configuração do cliente
# ══════════════════════════════════════════════════════════════════════
brief = load_brief()

with st.sidebar:
    st.markdown("### Configuração do Cliente")

    client_name = st.text_input("Nome do cliente", value=brief.get("client_name", ""))
    niche = st.text_input("Nicho", value=brief.get("niche", ""))

    current_tone = brief.get("tone_of_voice", TONES[0])
    tone_index = TONES.index(current_tone) if current_tone in TONES else 0
    tone = st.selectbox("Tom de voz", TONES, index=tone_index)

    current_formats = brief.get("formats", ["Reels/TikTok curtos"])
    formats = st.multiselect("Formatos", FORMATS, default=current_formats)

    if st.button("Salvar configuração", use_container_width=True, type="primary"):
        if client_name and niche and formats:
            save_brief(client_name, niche, tone, formats)
            st.success("Configuração salva")
        else:
            st.error("Preencha nome, nicho e pelo menos um formato")

    # Status rápido
    st.divider()
    st.markdown("### Status")

    n_trans = count_files(TRANSCRIPTIONS_DIR)
    n_scripts = 0
    scripts_data = read_json_safe(SCRIPTS_DIR / "scripts_raw.json")
    if isinstance(scripts_data, list):
        n_scripts = len(scripts_data)
    n_pdfs = count_files(OUTPUT_DIR, "*.pdf")

    research = read_json_safe(INPUTS_DIR / "manus_research.json")
    n_videos = len(research.get("viral_videos", [])) if research else 0

    col1, col2 = st.columns(2)
    col1.metric("Vídeos pesquisa", n_videos)
    col2.metric("Transcrições", n_trans)
    col1.metric("Roteiros", f"{n_scripts}/30")
    col2.metric("PDFs", n_pdfs)


# ══════════════════════════════════════════════════════════════════════
# ÁREA PRINCIPAL — Tabs
# ══════════════════════════════════════════════════════════════════════
st.markdown(f"## {client_name or 'Novo Cliente'}")

tab_research, tab_pipeline, tab_result = st.tabs([
    "Pesquisa Manus", "Pipeline", "Resultado"
])

# ── TAB 1: Pesquisa Manus ────────────────────────────────────────────
with tab_research:
    col_prompt, col_import = st.columns(2)

    with col_prompt:
        st.markdown("#### Gerar Prompt")
        if st.button("Gerar prompt para Manus", use_container_width=True):
            if niche:
                prompt = generate_manus_prompt(niche, client_name, tone)
                st.session_state["manus_prompt"] = prompt
            else:
                st.error("Preencha o nicho na sidebar")

        if "manus_prompt" in st.session_state:
            st.text_area(
                "Copie e cole na Manus:",
                st.session_state["manus_prompt"],
                height=300,
            )

    with col_import:
        st.markdown("#### Importar Resposta")
        manus_text = st.text_area(
            "Cole a resposta da Manus aqui (JSON ou tabela):",
            height=300,
            key="manus_response",
        )

        if st.button("Importar pesquisa", use_container_width=True, type="primary"):
            if manus_text.strip():
                parsed = parse_manus_response(manus_text)
                if parsed and parsed.get("viral_videos"):
                    write_json_file(INPUTS_DIR / "manus_research.json", parsed)
                    n_profiles = len(parsed.get("profiles", []))
                    n_vids = len(parsed["viral_videos"])
                    st.success(f"Importado: {n_profiles} perfis, {n_vids} vídeos")
                    st.rerun()
                else:
                    st.error("Não foi possível parsear. Verifique o formato (JSON ou tabela markdown).")
            else:
                st.warning("Cole a resposta da Manus primeiro")

    # Mostrar pesquisa atual
    if research and research.get("viral_videos"):
        st.divider()
        st.markdown(f"#### Pesquisa atual: {len(research['viral_videos'])} vídeos")
        for v in research["viral_videos"][:5]:
            st.markdown(f"- `{v.get('profile', '')}` — {v.get('description', '')[:60]}")
        if len(research["viral_videos"]) > 5:
            st.caption(f"... e mais {len(research['viral_videos']) - 5} vídeos")


# ── TAB 2: Pipeline ──────────────────────────────────────────────────
with tab_pipeline:
    st.markdown("#### Controle do Pipeline")

    # Botão principal
    col_main, col_clean = st.columns([3, 1])

    with col_main:
        run_all = st.button(
            "Rodar Pipeline Completo (Etapas 1 → 4)",
            use_container_width=True,
            type="primary",
        )

    with col_clean:
        if st.button("Limpar dados", use_container_width=True):
            for d in [TRANSCRIPTIONS_DIR, ANALYSIS_DIR, SCRIPTS_DIR, OUTPUT_DIR]:
                if d.exists():
                    for f in d.iterdir():
                        if f.is_file():
                            f.unlink()
            st.success("Dados limpos")
            st.rerun()

    st.divider()

    # Botões individuais
    st.markdown("#### Etapas individuais")
    cols = st.columns(4)

    individual_runs = {}
    for i, (step_num, info) in enumerate(STEPS_INFO.items()):
        with cols[i]:
            individual_runs[step_num] = st.button(
                f"{info['icon']} {info['name']}",
                use_container_width=True,
                key=f"step_{step_num}",
            )

    st.divider()

    # Execução
    steps_to_run = []
    if run_all:
        steps_to_run = [1, 2, 3, 4]
    else:
        for step_num, clicked in individual_runs.items():
            if clicked:
                steps_to_run = [step_num]
                break

    if steps_to_run:
        # Validações
        if not client_name or not niche:
            st.error("Configure nome e nicho do cliente na sidebar antes de rodar.")
        elif steps_to_run[0] == 1 and not n_videos:
            st.error("Importe a pesquisa da Manus primeiro (aba Pesquisa Manus).")
        else:
            save_brief(client_name, niche, tone, formats)

            total_start = time.time()
            results = {}

            for step_num in steps_to_run:
                info = STEPS_INFO[step_num]

                with st.status(
                    f"{info['icon']} Etapa {step_num}: {info['name']}...",
                    expanded=True,
                ) as status:
                    output_area = st.empty()
                    start = time.time()

                    ok, output = run_script(info["script"], output_area)

                    elapsed = time.time() - start
                    results[step_num] = {"ok": ok, "time": elapsed, "output": output}

                    if ok:
                        status.update(
                            label=f"{info['icon']} {info['name']} — OK ({int(elapsed)}s)",
                            state="complete",
                        )
                    else:
                        status.update(
                            label=f"{info['icon']} {info['name']} — ERRO",
                            state="error",
                        )

            total_elapsed = time.time() - total_start
            st.divider()

            # Resumo
            success_count = sum(1 for r in results.values() if r["ok"])
            total_count = len(results)

            if success_count == total_count:
                st.success(f"Pipeline concluído em {int(total_elapsed)}s — {success_count}/{total_count} etapas OK")
            else:
                st.warning(f"Pipeline concluído com erros — {success_count}/{total_count} etapas OK")

            st.rerun()


# ── TAB 3: Resultado ─────────────────────────────────────────────────
with tab_result:
    # Métricas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""<div class="metric-box">
            <div class="metric-num">{n_videos}</div>
            <div class="metric-label">Vídeos Pesquisados</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown(f"""<div class="metric-box">
            <div class="metric-num">{n_trans}</div>
            <div class="metric-label">Transcrições</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        st.markdown(f"""<div class="metric-box">
            <div class="metric-num">{n_scripts}/30</div>
            <div class="metric-label">Roteiros Gerados</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        st.markdown(f"""<div class="metric-box">
            <div class="metric-num">{n_pdfs}</div>
            <div class="metric-label">PDFs Gerados</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # Análise de padrões
    patterns = read_json_safe(ANALYSIS_DIR / "viral_patterns.json")
    if patterns:
        st.markdown("#### Padrões Virais Identificados")

        p_col1, p_col2, p_col3 = st.columns(3)

        with p_col1:
            st.markdown("**Ganchos**")
            for h in patterns.get("hook_patterns", []):
                st.markdown(f"- **{h.get('type', '')}**: {h.get('description', '')[:50]}")

        with p_col2:
            st.markdown("**Gatilhos Emocionais**")
            for t in patterns.get("emotional_triggers", []):
                st.markdown(f"- **{t.get('trigger', '')}**: {t.get('description', '')[:50]}")

        with p_col3:
            st.markdown("**CTAs**")
            for c in patterns.get("cta_types", []):
                st.markdown(f"- **{c.get('type', '')}**: {c.get('example', '')[:50]}")

        if patterns.get("key_insights"):
            st.markdown("**Insights principais:**")
            for insight in patterns["key_insights"]:
                st.info(insight)

    # Roteiros
    if isinstance(scripts_data, list) and scripts_data:
        st.divider()
        st.markdown("#### Roteiros Gerados")

        for s in scripts_data:
            num = s.get("number", "?")
            title = s.get("title", "Sem título")
            hook_type = s.get("hook", {}).get("type", "")
            objective = s.get("objective", "")
            with st.expander(f"#{num:02d} — {title}  |  {hook_type} · {objective}"):
                hook = s.get("hook", {})
                st.markdown(f"**Gancho:** \"{hook.get('text', '')}\"")
                for block in s.get("body", []):
                    if isinstance(block, dict):
                        st.markdown(f"**Bloco {block.get('block_number', '')}** ({block.get('time_range', '')})")
                        st.markdown(block.get("script", ""))
                cta = s.get("cta", {})
                st.markdown(f"**CTA:** {cta.get('text', '')}")

    # Download PDF
    st.divider()
    pdfs = sorted(OUTPUT_DIR.glob("*.pdf")) if OUTPUT_DIR.exists() else []
    if pdfs:
        st.markdown("#### Download")
        for pdf in pdfs:
            with open(pdf, "rb") as f:
                st.download_button(
                    f"Baixar {pdf.name}",
                    data=f.read(),
                    file_name=pdf.name,
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
    else:
        st.info("Nenhum PDF gerado ainda. Rode o pipeline para gerar.")
