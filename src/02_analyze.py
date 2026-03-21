"""
Etapa 4 — Análise de padrões virais.

Lê todas as transcrições e usa GPT-4o (OpenAI) para extrair
o Dicionário de Padrões Virais do nicho.
"""

import json
import os

from openai import OpenAI

from utils import (
    ANALYSIS_DIR,
    TRANSCRIPTIONS_DIR,
    load_env,
    read_client_brief,
    read_json,
    setup_logging,
    write_json,
)

logger = setup_logging("02_analyze")

SYSTEM_PROMPT = """Você é um especialista em marketing de conteúdo viral.
Sua função é analisar transcrições de vídeos virais e extrair padrões
replicáveis de forma estruturada em JSON."""

ANALYSIS_PROMPT = """Abaixo estão transcrições de {count} vídeos do nicho de "{niche}"
que geraram alta performance nas redes sociais.

Analise TODAS as transcrições e extraia:

1. **Padrões de gancho** (primeiros 3 segundos) — liste cada tipo de gancho encontrado
   com exemplo literal do vídeo e frequência de uso
2. **Estrutura narrativa dominante** — ex: problema > amplificação > solução > CTA,
   ou variações. Identifique o padrão mais comum e variações.
3. **Gatilhos emocionais mais usados** — curiosidade, medo de perda, pertencimento,
   autoridade, urgência, etc. Com exemplos de cada.
4. **Vocabulário e expressões recorrentes do nicho** — palavras e frases que aparecem
   em múltiplos vídeos virais.
5. **Timing médio por seção** — quanto tempo dura cada parte (gancho, desenvolvimento,
   CTA) nos vídeos analisados.
6. **Tipos de CTA** — os calls-to-action mais usados e seus formatos.
7. **Elementos de diferenciação** — o que rompe o padrão e chama atenção,
   o que torna certos vídeos muito mais virais que outros.
8. **Padrões de câmera/visual deduzíveis** — quando mencionado ou deduzível da
   transcrição (fala direta, referência a texto na tela, b-roll, etc.)

Retorne APENAS um JSON válido (sem markdown, sem blocos de código), com esta estrutura exata:

{{
  "hook_patterns": [
    {{
      "type": "nome do tipo de gancho",
      "description": "como funciona",
      "examples": ["exemplo 1", "exemplo 2"],
      "frequency": "X de Y vídeos"
    }}
  ],
  "narrative_structures": [
    {{
      "name": "nome da estrutura",
      "steps": ["passo 1", "passo 2", "..."],
      "frequency": "X de Y vídeos"
    }}
  ],
  "emotional_triggers": [
    {{
      "trigger": "nome do gatilho",
      "description": "como é usado",
      "examples": ["exemplo do vídeo"],
      "frequency": "X de Y vídeos"
    }}
  ],
  "niche_vocabulary": [
    {{
      "term": "palavra ou expressão",
      "context": "como é usada",
      "frequency": "X de Y vídeos"
    }}
  ],
  "timing": {{
    "avg_total_duration": "Xs",
    "hook": "Xs",
    "development": "Xs",
    "cta": "Xs"
  }},
  "cta_types": [
    {{
      "type": "tipo de CTA",
      "example": "exemplo literal",
      "frequency": "X de Y vídeos"
    }}
  ],
  "differentiation_elements": [
    {{
      "element": "nome do elemento",
      "description": "por que funciona",
      "examples": ["exemplo"]
    }}
  ],
  "visual_patterns": [
    {{
      "pattern": "nome do padrão visual",
      "description": "como aparece nos vídeos",
      "frequency": "X de Y vídeos"
    }}
  ],
  "niche": "{niche}",
  "total_videos_analyzed": {count},
  "key_insights": [
    "insight resumido 1",
    "insight resumido 2",
    "insight resumido 3"
  ]
}}

=== TRANSCRIÇÕES ===
{transcriptions}"""


def load_transcriptions() -> list[dict]:
    """Carrega todas as transcrições da pasta."""
    files = sorted(TRANSCRIPTIONS_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(
            f"Nenhuma transcrição encontrada em {TRANSCRIPTIONS_DIR}. "
            "Execute 01_transcribe.py primeiro."
        )

    transcriptions = []
    for f in files:
        data = read_json(f)
        transcriptions.append(data)
        logger.info(f"Carregada: {f.name} — {len(data.get('transcription', ''))} chars")

    logger.info(f"Total de transcrições carregadas: {len(transcriptions)}")
    return transcriptions


def format_transcriptions_for_prompt(transcriptions: list[dict]) -> str:
    """Formata transcrições para o prompt de análise."""
    parts = []
    for i, t in enumerate(transcriptions, 1):
        metrics = t.get("metrics", {})
        header = (
            f"\n--- VÍDEO {i} ---\n"
            f"Perfil: {t.get('profile', 'N/A')}\n"
            f"Plataforma: {t.get('platform', 'N/A')}\n"
            f"Views: {metrics.get('views', 'N/A')} | "
            f"Likes: {metrics.get('likes', 'N/A')} | "
            f"Comentários: {metrics.get('comments', 'N/A')}\n"
            f"Duração: {t.get('duration', 'N/A')}s\n"
            f"Transcrição:\n{t.get('transcription', '[sem transcrição]')}\n"
        )
        parts.append(header)
    return "\n".join(parts)


def analyze_patterns(transcriptions: list[dict], niche: str) -> dict:
    """Envia transcrições para GPT-4o e extrai padrões virais."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    formatted = format_transcriptions_for_prompt(transcriptions)

    user_prompt = ANALYSIS_PROMPT.format(
        count=len(transcriptions),
        niche=niche,
        transcriptions=formatted,
    )

    logger.info(f"Enviando {len(transcriptions)} transcrições para análise (GPT-4o)...")
    logger.debug(f"Tamanho do prompt: {len(user_prompt)} caracteres")

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=8000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_text = response.choices[0].message.content.strip()

    # Tentar parsear como JSON
    try:
        patterns = json.loads(raw_text)
    except json.JSONDecodeError:
        # Tentar extrair JSON do texto (pode vir com ```json ... ```)
        cleaned = raw_text
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1]
        if "```" in cleaned:
            cleaned = cleaned.split("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            patterns = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                patterns = json.loads(cleaned[start:end])
            else:
                logger.error(f"Resposta não é JSON válido: {raw_text[:500]}")
                raise ValueError("GPT-4o não retornou JSON válido na análise")

    logger.info(f"Análise concluída: {len(patterns.get('hook_patterns', []))} padrões de gancho, "
                f"{len(patterns.get('emotional_triggers', []))} gatilhos emocionais")

    return patterns


def main():
    load_env()
    ANALYSIS_DIR.mkdir(exist_ok=True)

    brief = read_client_brief()
    niche = brief["niche"]
    logger.info(f"Nicho: {niche}")

    transcriptions = load_transcriptions()
    patterns = analyze_patterns(transcriptions, niche)

    output_path = ANALYSIS_DIR / "viral_patterns.json"
    write_json(output_path, patterns)
    logger.info(f"Dicionário de padrões virais salvo em: {output_path}")

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DA ANÁLISE")
    print("=" * 60)
    print(f"Vídeos analisados: {patterns.get('total_videos_analyzed', 'N/A')}")
    print(f"Padrões de gancho: {len(patterns.get('hook_patterns', []))}")
    print(f"Estruturas narrativas: {len(patterns.get('narrative_structures', []))}")
    print(f"Gatilhos emocionais: {len(patterns.get('emotional_triggers', []))}")
    print(f"Vocabulário do nicho: {len(patterns.get('niche_vocabulary', []))}")
    print(f"Tipos de CTA: {len(patterns.get('cta_types', []))}")
    if patterns.get("key_insights"):
        print("\nInsights principais:")
        for insight in patterns["key_insights"]:
            print(f"  • {insight}")
    print("=" * 60)


if __name__ == "__main__":
    main()
