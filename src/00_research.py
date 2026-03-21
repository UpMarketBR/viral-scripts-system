"""
Etapa 2 — Pesquisa automatizada via Manus.

Modo 1 (gerar prompt): Lê o brief e gera o prompt pronto para colar na Manus.
Modo 2 (importar):      Cola a resposta da Manus e converte para manus_research.json.
"""

import json
import re
import sys

from utils import INPUTS_DIR, read_client_brief, setup_logging, write_json

logger = setup_logging("00_research")

MANUS_PROMPT_TEMPLATE = """Preciso que você pesquise os perfis mais virais no nicho de "{niche}" nas redes sociais (Instagram, TikTok e YouTube).

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
- Para Instagram, use o formato: https://www.instagram.com/reel/CODIGO/
- Para YouTube, use: https://www.youtube.com/watch?v=CODIGO ou https://www.youtube.com/shorts/CODIGO
- Para TikTok, use: https://www.tiktok.com/@handle/video/CODIGO
- Inclua métricas reais (views, likes, comentários) — se não encontrar o número exato, estime.
- Mínimo de 15 vídeos, máximo de 25.
- O JSON deve ser válido e parseável diretamente.

NICHO: {niche}
CONTEXTO: {context}
"""


def generate_prompt():
    """Gera o prompt para colar na Manus."""
    brief = read_client_brief()
    niche = brief["niche"]
    context = (
        f"Cliente: {brief['client_name']}. "
        f"Avatar: {brief['avatar']}. "
        f"Tom de voz: {brief['tone_of_voice']}. "
        f"Diferencial: {brief['differentiator']}."
    )

    prompt = MANUS_PROMPT_TEMPLATE.format(niche=niche, context=context)

    prompt_path = INPUTS_DIR / "manus_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    print("=" * 60)
    print("PROMPT PARA A MANUS (copiado para inputs/manus_prompt.txt)")
    print("=" * 60)
    print(prompt)
    print("=" * 60)
    print(f"\nArquivo salvo: {prompt_path}")
    print("\nPróximo passo:")
    print("  1. Cole este prompt na Manus")
    print("  2. Copie a resposta da Manus")
    print("  3. Rode: python 00_research.py importar")
    print("     (vai pedir para colar a resposta)")


def extract_json_from_text(text: str) -> dict:
    """Extrai JSON de qualquer texto (incluindo markdown, tabelas, etc.)."""
    # Tentar JSON direto
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Tentar extrair bloco ```json ... ```
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Tentar extrair qualquer JSON grande
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Tentar parsear tabela markdown
    return parse_markdown_table(text)


def parse_markdown_table(text: str) -> dict:
    """Parseia tabela markdown como a que o usuário colou da Manus."""
    profiles = {}
    videos = []

    # Encontrar linhas de tabela (com |)
    lines = [l.strip() for l in text.split("\n") if "|" in l and "---" not in l]

    if len(lines) < 2:
        raise ValueError("Não foi possível parsear a resposta da Manus. "
                         "Cole a resposta em formato JSON ou tabela markdown.")

    # Pular header
    header = lines[0]
    data_lines = lines[1:]

    for line in data_lines:
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 4:
            continue

        profile_name = cols[0].strip()
        profile_url = ""
        video_desc = ""
        video_url = ""

        # Extrair URLs de markdown links [texto](url)
        for i, col in enumerate(cols):
            urls = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', col)
            plain_urls = re.findall(r'(https?://\S+)', col)
            all_urls = urls or plain_urls

            if i == 1 and all_urls:  # coluna do perfil
                profile_url = all_urls[0]
            elif i == 2:  # descrição
                video_desc = re.sub(r'\[.*?\]\(.*?\)', '', col).strip().strip('"')
                if not video_desc:
                    video_desc = col.strip()
            elif i == 3 and all_urls:  # URL do vídeo
                video_url = all_urls[0]

        # Detectar plataforma
        platform = "instagram"
        if "youtube.com" in video_url or "youtu.be" in video_url:
            platform = "youtube"
        elif "tiktok.com" in video_url:
            platform = "tiktok"

        # Extrair handle
        handle = ""
        handle_match = re.search(r'instagram\.com/([^/?]+)', profile_url)
        if handle_match:
            handle = f"@{handle_match.group(1)}"
        else:
            handle_match = re.search(r'tiktok\.com/@([^/?]+)', profile_url)
            if handle_match:
                handle = f"@{handle_match.group(1)}"

        # Adicionar perfil
        if profile_name and profile_name not in profiles:
            profiles[profile_name] = {
                "name": profile_name,
                "handle": handle,
                "platform": platform,
                "followers": 0,
                "avg_engagement": 0,
            }

        # Adicionar vídeo (apenas se tiver URL real de vídeo, não de perfil)
        if video_url and "/reel/" in video_url or "/p/" in video_url or \
           "watch?v=" in video_url or "/shorts/" in video_url or \
           "/video/" in video_url:
            videos.append({
                "url": video_url,
                "profile": handle or profile_name,
                "platform": platform,
                "views": 0,
                "likes": 0,
                "comments": 0,
                "description": video_desc,
            })

    if not videos:
        raise ValueError("Nenhum vídeo encontrado na resposta. Verifique o formato.")

    return {
        "profiles": list(profiles.values()),
        "viral_videos": videos,
    }


def import_response():
    """Importa resposta da Manus (JSON, tabela ou texto)."""
    print("Cole a resposta da Manus abaixo.")
    print("Pode ser JSON, tabela markdown ou texto livre.")
    print("Quando terminar, digite uma linha com apenas 'FIM' e pressione Enter.")
    print("-" * 40)

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "FIM":
                break
            lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)

    if not text.strip():
        print("Nenhum texto recebido. Abortando.")
        return

    logger.info(f"Recebido {len(text)} caracteres da Manus")

    data = extract_json_from_text(text)

    # Validar estrutura
    if "viral_videos" not in data:
        data["viral_videos"] = []
    if "profiles" not in data:
        data["profiles"] = []

    # Filtrar vídeos sem URL
    data["viral_videos"] = [v for v in data["viral_videos"] if v.get("url")]

    output_path = INPUTS_DIR / "manus_research.json"
    write_json(output_path, data)

    print("\n" + "=" * 60)
    print("PESQUISA IMPORTADA COM SUCESSO")
    print("=" * 60)
    print(f"Perfis: {len(data['profiles'])}")
    print(f"Vídeos: {len(data['viral_videos'])}")
    print(f"Salvo em: {output_path}")
    print("\nPróximo passo: python 01_transcribe.py")
    print("=" * 60)


def import_from_file(filepath: str):
    """Importa resposta da Manus de um arquivo."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    logger.info(f"Lendo resposta da Manus de {filepath} ({len(text)} chars)")

    data = extract_json_from_text(text)

    if "viral_videos" not in data:
        data["viral_videos"] = []
    if "profiles" not in data:
        data["profiles"] = []

    data["viral_videos"] = [v for v in data["viral_videos"] if v.get("url")]

    output_path = INPUTS_DIR / "manus_research.json"
    write_json(output_path, data)

    print(f"Importado: {len(data['profiles'])} perfis, {len(data['viral_videos'])} vídeos")
    print(f"Salvo em: {output_path}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "prompt":
        generate_prompt()
    elif sys.argv[1] == "importar":
        if len(sys.argv) > 2:
            import_from_file(sys.argv[2])
        else:
            import_response()
    else:
        print("Uso:")
        print("  python 00_research.py            → Gera prompt para a Manus")
        print("  python 00_research.py prompt      → Gera prompt para a Manus")
        print("  python 00_research.py importar    → Cola resposta da Manus (interativo)")
        print("  python 00_research.py importar arquivo.txt  → Importa de arquivo")


if __name__ == "__main__":
    main()
