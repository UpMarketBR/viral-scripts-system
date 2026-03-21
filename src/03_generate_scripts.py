"""
Etapa 5 — Geração dos 30 roteiros.

Usa o Dicionário de Padrões Virais + brief do cliente
para gerar 30 roteiros únicos via GPT-4o (OpenAI).
"""

import json
import os
import random

from openai import OpenAI

from utils import (
    ANALYSIS_DIR,
    SCRIPTS_DIR,
    load_env,
    read_client_brief,
    read_json,
    setup_logging,
    write_json,
)

logger = setup_logging("03_generate_scripts")

OBJECTIVES = ["awareness", "engajamento", "conversão", "autoridade", "comunidade", "educação", "entretenimento"]

HOOK_TYPES = [
    "pergunta provocativa",
    "estatística chocante",
    "afirmação polêmica",
    "história pessoal",
    "demonstração visual",
    "desafio direto",
    "promessa de resultado",
    "comparação inesperada",
]

SYSTEM_PROMPT = """Você é um roteirista especialista em conteúdo viral para redes sociais.
Sua função é criar roteiros completos, com falas exatas e guia de câmera detalhado,
baseados em padrões virais validados por dados reais. Retorne sempre JSON puro, sem markdown."""

GENERATION_PROMPT = """Crie o roteiro #{number} de 30.

DADOS DO CLIENTE:
- Nome: {client_name}
- Nicho: {niche}
- Tom de voz: {tone}
- Avatar (público-alvo): {avatar}
- Diferencial: {differentiator}

PADRÕES VIRAIS DO NICHO:
{patterns_json}

INSTRUÇÕES:
- Formato: {format}
- Duração estimada: {duration}
- Objetivo deste roteiro: {objective}
- Este é o roteiro {number} de 30
- Roteiros anteriores: {previous_titles}
- O gancho NÃO pode começar igual a nenhum roteiro anterior
- OBRIGATÓRIO: O tipo de gancho deste roteiro DEVE ser: {required_hook_type}
- Use um tipo de gancho diferente do roteiro anterior (anterior usou: {last_hook_type})
- Aplique os padrões validados mas com a VOZ AUTÊNTICA do cliente
- O guia de câmera deve ser detalhado o suficiente para alguém sem experiência executar
- Adapte os padrões, NÃO copie os vídeos analisados

Retorne APENAS um JSON válido (sem markdown, sem blocos de código), com esta estrutura:

{{
  "number": {number},
  "title": "título interno do roteiro (referência, não vai a público)",
  "format": "{format}",
  "estimated_duration": "{duration}",
  "objective": "{objective}",
  "hook": {{
    "type": "tipo do gancho usado (pergunta, estatística, polêmica, história, demonstração, desafio, promessa, etc.)",
    "text": "texto exato dos primeiros 3 segundos — o que é FALADO",
    "screen_text": "texto que aparece na tela (se aplicável, senão null)",
    "action": "ação visual do apresentador neste momento"
  }},
  "body": [
    {{
      "block_number": 1,
      "time_range": "0:03 - 0:15",
      "script": "texto exato que o apresentador fala neste bloco",
      "camera_guide": {{
        "position": "posição da câmera (altura, ângulo, distância)",
        "framing": "enquadramento (fechado, médio, aberto)",
        "movement": "movimento (estático, zoom in, câmera na mão, etc.)",
        "lighting": "iluminação (frontal, lateral, natural)",
        "production_notes": "b-roll, texto na tela, música, efeitos"
      }}
    }}
  ],
  "cta": {{
    "text": "texto exato do CTA final",
    "type": "tipo de CTA (seguir, comentar, compartilhar, link, etc.)"
  }},
  "viral_pattern_reference": "qual insight/padrão da análise este roteiro aplica e por quê"
}}"""


def distribute_objectives(count: int = 30) -> list[str]:
    """Distribui objetivos garantindo pelo menos 4 diferentes."""
    base = OBJECTIVES[:4] * (count // 4)
    remaining = count - len(base)
    base.extend(random.sample(OBJECTIVES, min(remaining, len(OBJECTIVES))))
    base = base[:count]
    random.shuffle(base)
    # Garantir que não há dois iguais consecutivos
    for i in range(1, len(base)):
        if base[i] == base[i - 1]:
            for j in range(len(base)):
                if j != i and j != i - 1 and base[j] != base[i - 1]:
                    if j + 1 >= len(base) or base[j + 1] != base[i]:
                        if j - 1 < 0 or base[j - 1] != base[i]:
                            base[i], base[j] = base[j], base[i]
                            break
    return base


def distribute_hooks(count: int = 30) -> list[str]:
    """Distribui tipos de gancho ciclicamente, garantindo variedade (no two consecutive equal)."""
    hooks: list[str] = []
    pool = list(HOOK_TYPES)
    random.shuffle(pool)

    for i in range(count):
        candidate = pool[i % len(pool)]
        # Ensure no two consecutive hooks are the same type
        if hooks and candidate == hooks[-1]:
            # Pick the next different type from the pool
            for offset in range(1, len(pool)):
                alt = pool[(i + offset) % len(pool)]
                if alt != hooks[-1]:
                    candidate = alt
                    break
        hooks.append(candidate)

    return hooks


def distribute_formats(client_formats: list[str], count: int = 30) -> list[tuple[str, str]]:
    """Distribui formatos com duração estimada."""
    format_durations = {
        "Reels/TikTok curtos": "30-60 segundos",
        "YouTube Shorts": "30-60 segundos",
        "Stories": "15-30 segundos",
        "vídeos médios": "1-3 minutos",
    }

    if not client_formats:
        client_formats = ["Reels/TikTok curtos"]

    formats = []
    for i in range(count):
        fmt = client_formats[i % len(client_formats)]
        duration = format_durations.get(fmt, "30-60 segundos")
        formats.append((fmt, duration))

    random.shuffle(formats)
    return formats


def parse_json_response(raw_text: str, number: int) -> dict:
    """Parseia resposta JSON do GPT, lidando com markdown."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Remover blocos de código markdown
    cleaned = raw_text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
    if "```" in cleaned:
        cleaned = cleaned.split("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(cleaned[start:end])

    raise ValueError(f"GPT-4o não retornou JSON válido para roteiro #{number}")


def generate_single_script(
    client: OpenAI,
    brief: dict,
    patterns: dict,
    number: int,
    fmt: str,
    duration: str,
    objective: str,
    previous_titles: list[str],
    last_hook_type: str,
    hook_type: str = "variado",
) -> dict:
    """Gera um único roteiro via GPT-4o."""

    prev_str = ", ".join(previous_titles[-10:]) if previous_titles else "nenhum (este é o primeiro)"

    prompt = GENERATION_PROMPT.format(
        number=number,
        client_name=brief["client_name"],
        niche=brief["niche"],
        tone=brief["tone_of_voice"],
        avatar=brief["avatar"],
        differentiator=brief["differentiator"],
        patterns_json=json.dumps(patterns, ensure_ascii=False, indent=1),
        format=fmt,
        duration=duration,
        objective=objective,
        previous_titles=prev_str,
        last_hook_type=last_hook_type,
        required_hook_type=hook_type,
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.8,
        max_tokens=4000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    raw_text = response.choices[0].message.content.strip()
    script = parse_json_response(raw_text, number)
    script["number"] = number
    return script


def main():
    load_env()
    SCRIPTS_DIR.mkdir(exist_ok=True)

    brief = read_client_brief()
    patterns = read_json(ANALYSIS_DIR / "viral_patterns.json")

    logger.info(f"Cliente: {brief['client_name']} | Nicho: {brief['niche']}")
    logger.info(f"Formatos: {brief['formats']}")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    objectives = distribute_objectives(30)
    formats = distribute_formats(brief["formats"], 30)
    hooks = distribute_hooks(30)

    scripts = []
    previous_titles = []
    last_hook_type = "nenhum"

    # Verificar se há roteiros já gerados (para retomar)
    existing_path = SCRIPTS_DIR / "scripts_raw.json"
    if existing_path.exists():
        existing = read_json(existing_path)
        if isinstance(existing, list) and len(existing) > 0:
            scripts = existing
            previous_titles = [s.get("title", "") for s in scripts]
            last_hook_type = scripts[-1].get("hook", {}).get("type", "nenhum")
            logger.info(f"Retomando a partir do roteiro #{len(scripts) + 1}")

    start_from = len(scripts) + 1

    for i in range(start_from, 31):
        idx = i - 1
        fmt, duration = formats[idx]
        objective = objectives[idx]
        hook_type = hooks[idx]

        logger.info(f"Gerando roteiro #{i}/30 — {fmt} — {objective} — gancho: {hook_type}")

        try:
            script = generate_single_script(
                client=client,
                brief=brief,
                patterns=patterns,
                number=i,
                fmt=fmt,
                duration=duration,
                objective=objective,
                previous_titles=previous_titles,
                last_hook_type=last_hook_type,
                hook_type=hook_type,
            )

            scripts.append(script)
            previous_titles.append(script.get("title", f"Roteiro {i}"))
            last_hook_type = script.get("hook", {}).get("type", "nenhum")

            # Salvar incrementalmente
            write_json(existing_path, scripts)

            logger.info(f"Roteiro #{i}: {script.get('title', 'sem titulo')} "
                        f"[gancho: {last_hook_type}]")

        except Exception as e:
            logger.error(f"Erro no roteiro #{i}: {e}")
            continue

    # Salvar versão final
    write_json(existing_path, scripts)
    logger.info(f"Geração finalizada: {len(scripts)} roteiros salvos em {existing_path}")

    # Validações
    hook_types = set(s.get("hook", {}).get("type", "") for s in scripts)
    obj_types = set(s.get("objective", "") for s in scripts)
    fmt_types = set(s.get("format", "") for s in scripts)

    print("\n" + "=" * 60)
    print("RESUMO DA GERAÇÃO")
    print("=" * 60)
    print(f"Roteiros gerados: {len(scripts)}/30")
    print(f"Tipos de gancho únicos: {len(hook_types)} (mínimo: 5)")
    print(f"Objetivos únicos: {len(obj_types)} (mínimo: 4)")
    print(f"Formatos únicos: {len(fmt_types)} (mínimo: {'3' if len(brief['formats']) >= 3 else '1'})")

    if len(hook_types) < 5:
        print("AVISO: Menos de 5 tipos de gancho diferentes")
    if len(obj_types) < 4:
        print("AVISO: Menos de 4 objetivos diferentes")
    print("=" * 60)


if __name__ == "__main__":
    main()
