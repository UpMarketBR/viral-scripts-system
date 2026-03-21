"""
Etapa 3 — Transcrição automática.

Para cada URL de vídeo da pesquisa Manus:
1. Baixa o áudio com yt-dlp
2. Transcreve com Whisper API (OpenAI)
3. Salva transcrição com metadados
"""

import os
import subprocess
from pathlib import Path

from openai import OpenAI

from utils import (
    TEMP_DIR,
    TRANSCRIPTIONS_DIR,
    load_env,
    read_manus_research,
    setup_logging,
    write_json,
)

logger = setup_logging("01_transcribe")

# Limite do Whisper API: 25 MB
MAX_FILE_SIZE_MB = 25

# Caminhos dos binários (Windows via winget)
YTDLP_BIN = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe"
)
FFMPEG_DIR = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-123074-g4e32fb4c2a-win64-gpl\bin"
)
FFMPEG_BIN = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

IS_CLOUD = not os.path.isfile(YTDLP_BIN)


def _ytdlp_cmd() -> str:
    if os.path.isfile(YTDLP_BIN):
        return YTDLP_BIN
    return "yt-dlp"


def download_audio(url: str, output_path: Path) -> Path:
    """Baixa o áudio de um vídeo usando yt-dlp."""
    cmd = [
        _ytdlp_cmd(),
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "-o", str(output_path),
        "--no-playlist",
        "--no-overwrites",
        url,
    ]
    # Adicionar ffmpeg-location se disponível localmente
    if not IS_CLOUD:
        cmd.insert(5, "--ffmpeg-location")
        cmd.insert(6, FFMPEG_DIR)
        # Cookies do Chrome só funcionam localmente
        cmd.insert(-1, "--cookies-from-browser")
        cmd.insert(-1, "chrome")
    logger.info(f"Baixando áudio: {url}")
    logger.debug(f"Comando: {' '.join(cmd)}")

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300
    )

    if result.returncode != 0:
        logger.error(f"yt-dlp falhou: {result.stderr}")
        raise RuntimeError(f"Falha ao baixar áudio de {url}: {result.stderr}")

    # yt-dlp pode adicionar extensão ao nome
    final_path = output_path.with_suffix(".mp3")
    if not final_path.exists():
        # Tenta encontrar o arquivo gerado
        candidates = list(output_path.parent.glob(f"{output_path.stem}.*"))
        if candidates:
            final_path = candidates[0]
        else:
            raise FileNotFoundError(f"Arquivo de áudio não encontrado após download: {output_path}")

    size_mb = final_path.stat().st_size / (1024 * 1024)
    logger.info(f"Áudio baixado: {final_path.name} ({size_mb:.1f} MB)")

    if size_mb > MAX_FILE_SIZE_MB:
        logger.warning(f"Arquivo excede {MAX_FILE_SIZE_MB} MB — comprimindo...")
        compressed = final_path.with_stem(final_path.stem + "_compressed")
        ffmpeg_cmd = FFMPEG_BIN if os.path.isfile(FFMPEG_BIN) else "ffmpeg"
        subprocess.run(
            [
                ffmpeg_cmd, "-i", str(final_path),
                "-b:a", "32k", "-ar", "16000", "-ac", "1",
                str(compressed), "-y",
            ],
            capture_output=True, timeout=120,
        )
        if compressed.exists() and compressed.stat().st_size < final_path.stat().st_size:
            final_path.unlink()
            compressed.rename(final_path)
            logger.info(f"Comprimido para {final_path.stat().st_size / (1024*1024):.1f} MB")

    return final_path


def transcribe_audio(client: OpenAI, audio_path: Path) -> dict:
    """Transcreve áudio usando Whisper API."""
    logger.info(f"Transcrevendo: {audio_path.name}")

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    result = {
        "text": response.text,
        "duration": response.duration,
        "segments": [],
    }

    if hasattr(response, "segments") and response.segments:
        for seg in response.segments:
            result["segments"].append({
                "start": seg["start"] if isinstance(seg, dict) else seg.start,
                "end": seg["end"] if isinstance(seg, dict) else seg.end,
                "text": seg["text"] if isinstance(seg, dict) else seg.text,
            })

    logger.info(f"Transcrição concluída: {len(result['text'])} caracteres, {result['duration']:.1f}s")
    return result


def process_video(client: OpenAI, video: dict, index: int) -> dict | None:
    """Processa um vídeo: download + transcrição."""
    url = video.get("url", "")
    if not url:
        logger.warning(f"Vídeo #{index}: URL vazia, pulando")
        return None

    video_id = f"video_{index:03d}"
    output_path = TRANSCRIPTIONS_DIR / f"{video_id}.json"

    # Pula se já transcrito
    if output_path.exists():
        logger.info(f"Vídeo #{index} já transcrito, pulando: {output_path.name}")
        return None

    try:
        # Download
        audio_path = TEMP_DIR / f"{video_id}"
        audio_file = download_audio(url, audio_path)

        # Transcrição
        transcription = transcribe_audio(client, audio_file)

        # Montar resultado
        result = {
            "video_id": video_id,
            "url": url,
            "profile": video.get("profile", ""),
            "platform": video.get("platform", ""),
            "description": video.get("description", ""),
            "metrics": {
                "views": video.get("views", 0),
                "likes": video.get("likes", 0),
                "comments": video.get("comments", 0),
            },
            "transcription": transcription["text"],
            "duration": transcription["duration"],
            "segments": transcription["segments"],
        }

        # Salvar
        write_json(output_path, result)
        logger.info(f"Salvo: {output_path.name}")

        # Limpar áudio temporário
        audio_file.unlink(missing_ok=True)

        return result

    except Exception as e:
        logger.error(f"Erro ao processar vídeo #{index} ({url}): {e}")
        return None


def main():
    load_env()
    TEMP_DIR.mkdir(exist_ok=True)
    TRANSCRIPTIONS_DIR.mkdir(exist_ok=True)

    research = read_manus_research()
    videos = research["viral_videos"]
    logger.info(f"Total de vídeos para transcrever: {len(videos)}")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    success = 0
    errors = 0

    for i, video in enumerate(videos, start=1):
        result = process_video(client, video, i)
        if result:
            success += 1
        elif result is None and not (TRANSCRIPTIONS_DIR / f"video_{i:03d}.json").exists():
            errors += 1

    logger.info(f"Transcrição finalizada: {success} novos, {errors} erros")
    logger.info(f"Total de transcrições em {TRANSCRIPTIONS_DIR}: "
                f"{len(list(TRANSCRIPTIONS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
