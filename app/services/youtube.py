import glob
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError, sanitize_filename

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com",
}
TEMPLATE_ARQUIVO = "%(title)s.%(ext)s"

log = logging.getLogger(__name__)


def extrair_video_id(url: str):
    """Retorna o ID de 11 caracteres de um link do YouTube, ou None."""
    url = (url or "").strip()
    if not url:
        return None
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url

    u = urlparse(url)
    host = (u.hostname or "").lower()
    partes = [p for p in u.path.split("/") if p]
    video_id = None

    if host == "youtu.be":
        video_id = partes[0] if partes else None
    elif host in HOSTS:
        if u.path == "/watch":
            video_id = parse_qs(u.query).get("v", [None])[0]
        elif len(partes) >= 2 and partes[0] in ("shorts", "embed", "live", "v"):
            video_id = partes[1]

    return video_id if video_id and ID_RE.match(video_id) else None


def normalizar_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def resumir_infos(info: dict) -> dict:
    return {
        "titulo": info.get("title"),
        "canal": info.get("uploader"),
        "duracao": info.get("duration"),
        "url": info.get("webpage_url"),
        "data_publicacao": info.get("upload_date"),
    }


def nome_arquivo_legado(titulo: str) -> str:
    """Nome (sem extensão) que o yt-dlp gera a partir do título com o template padrão."""
    return sanitize_filename(titulo)


class DownloadCancelado(Exception):
    pass


class _RastreadorDownload:
    """Acompanha um download do yt-dlp: verifica pedidos de cancelamento e
    registra os arquivos gerados para poder apagá-los se o download for abortado."""

    INTERVALO_VERIFICACAO = 1.0  # segundos entre consultas a deve_cancelar

    def __init__(self, pasta: Path, deve_cancelar: Callable[[], bool] | None):
        self.pasta = Path(pasta).resolve()
        self.deve_cancelar = deve_cancelar
        self.cancelado = False
        self.arquivos: set[Path] = set()
        # Arquivos completos que já existiam não devem ser apagados no cancelamento
        self.existentes = {p.resolve() for p in self.pasta.iterdir()} if self.pasta.exists() else set()
        self._ultima_verificacao = 0.0

    def _registrar(self, *nomes):
        for nome in nomes:
            if nome:
                self.arquivos.add(Path(nome).resolve())

    def _verificar(self, forcar=False):
        if not self.deve_cancelar:
            return
        agora = time.monotonic()
        if not forcar and agora - self._ultima_verificacao < self.INTERVALO_VERIFICACAO:
            return
        self._ultima_verificacao = agora
        if self.deve_cancelar():
            self.cancelado = True
            raise DownloadCancelado("Download cancelado pelo usuário.")

    def hook_progresso(self, d):
        self._registrar(d.get("filename"), d.get("tmpfilename"))
        self._verificar(forcar=d.get("status") == "finished")

    def hook_pos_processamento(self, d):
        info = d.get("info_dict") or {}
        self._registrar(info.get("filepath"), *(info.get("__files_to_merge") or []))
        # A junção pelo ffmpeg não pode ser interrompida no meio; verifica antes e depois
        self._verificar(forcar=True)

    def limpar(self):
        candidatos = set()
        for arq in self.arquivos:
            candidatos.update({
                arq,
                arq.with_name(arq.name + ".part"),
                arq.with_name(arq.name + ".ytdl"),
                arq.with_name(f"{arq.stem}.temp{arq.suffix}"),  # temporário da junção
                *arq.parent.glob(glob.escape(arq.name) + ".part-Frag*"),
            })

        temporario = (".part", ".ytdl")
        for c in candidatos:
            eh_temporario = c.name.endswith(temporario) or ".part-Frag" in c.name or ".temp." in c.name
            if c.parent != self.pasta or not c.is_file():
                continue
            if c in self.existentes and not eh_temporario:
                continue
            try:
                c.unlink()
                log.info("Arquivo removido após cancelamento: %s", c.name)
            except OSError as e:
                log.warning("Não foi possível remover %s: %s", c.name, e)


def localizar_ffmpeg(ffmpeg_location: str | None = None):
    """Caminho do ffmpeg configurado ou encontrado no PATH, ou None."""
    if ffmpeg_location:
        return ffmpeg_location if Path(ffmpeg_location).exists() else None
    return shutil.which("ffmpeg")


class YouTubeDownloader:
    def __init__(self, pasta_downloads: Path, ffmpeg_location: str | None = None):
        self.pasta_downloads = Path(pasta_downloads)
        self.ffmpeg = localizar_ffmpeg(ffmpeg_location)

    def _opcoes(self, **extras) -> dict:
        opcoes = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            # O YouTube exige um runtime JS; habilita Node além do Deno (padrão)
            "js_runtimes": {"deno": {}, "node": {}},
        }
        if self.ffmpeg:
            opcoes["ffmpeg_location"] = self.ffmpeg
        opcoes.update(extras)
        return opcoes

    def obter_infos(self, url: str) -> dict:
        with yt_dlp.YoutubeDL(self._opcoes()) as ydl:
            info = ydl.extract_info(url, download=False)
        return resumir_infos(info)

    def baixar(self, url: str, deve_cancelar: Callable[[], bool] | None = None) -> tuple[Path, dict]:
        """Baixa o vídeo e retorna (caminho do arquivo final, infos resumidas).

        `deve_cancelar` é consultado durante o download; se retornar True, o download
        é interrompido, os arquivos gerados são apagados e DownloadCancelado é lançado.
        Lança yt_dlp.utils.DownloadError em caso de falha.
        """
        if not self.ffmpeg:
            log.warning("ffmpeg não encontrado: tentando formato único com áudio (qualidade menor)")

        rastreador = _RastreadorDownload(self.pasta_downloads, deve_cancelar)
        opcoes = self._opcoes(
            # Sem ffmpeg não é possível juntar vídeo e áudio separados
            format="bestvideo*+bestaudio/best" if self.ffmpeg else "best",
            outtmpl=str(self.pasta_downloads.joinpath(TEMPLATE_ARQUIVO)),
            progress_hooks=[rastreador.hook_progresso],
            postprocessor_hooks=[rastreador.hook_pos_processamento],
        )
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                # O yt-dlp pode embrulhar a exceção do hook em um DownloadError
                if rastreador.cancelado:
                    rastreador.limpar()
                    raise DownloadCancelado("Download cancelado pelo usuário.") from e
                if not isinstance(e, DownloadError):
                    raise
                if self.ffmpeg or "format is not available" not in str(e):
                    raise
                raise DownloadError(
                    f"{e}\nO YouTube só oferece vídeo e áudio separados para este vídeo. "
                    "Instale o ffmpeg (winget install Gyan.FFmpeg) ou defina FFMPEG_LOCATION no .env."
                ) from e
            baixados = info.get("requested_downloads") or []
            caminho = baixados[0].get("filepath") if baixados else None
            if not caminho:
                caminho = ydl.prepare_filename(info)

        return Path(caminho), resumir_infos(info)
