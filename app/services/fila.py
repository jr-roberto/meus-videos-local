import logging
import time
from pathlib import Path

from flask import current_app
from sqlalchemy import select, update

from app.extensions import db
from app.models import Status, VideosDownload
from app.services.processo_worker import TravaWorker, caminho_trava
from app.services.youtube import DownloadCancelado, YouTubeDownloader, nome_arquivo_legado

log = logging.getLogger(__name__)


def _downloader():
    return YouTubeDownloader(
        current_app.config["PATH_DOWNLOADS"],
        ffmpeg_location=current_app.config["FFMPEG_LOCATION"],
    )


def caminho_arquivo(video: VideosDownload):
    """Caminho do arquivo baixado do vídeo, se existir dentro de PATH_DOWNLOADS."""
    pasta = Path(current_app.config["PATH_DOWNLOADS"]).resolve()
    candidatos = []

    if video.arquivo:
        candidatos.append(pasta.joinpath(video.arquivo))
    elif video.titulo_video and video.status_download == Status.CONCLUIDO:
        # Registros antigos não guardavam o nome do arquivo
        candidatos.extend(pasta.glob(f"{nome_arquivo_legado(video.titulo_video)}.*"))

    for c in candidatos:
        c = c.resolve()
        if c.is_file() and c.parent == pasta and not c.name.endswith(".part"):
            return c
    return None


def atualizar_infos():
    """Preenche título e metadados dos vídeos na fila que ainda não os têm."""
    pendentes = VideosDownload.query.filter(
        VideosDownload.status_download == Status.FILA,
        VideosDownload.titulo_video.is_(None),
    ).all()

    for video in pendentes:
        try:
            meta = _downloader().obter_infos(video.url_video)
        except Exception as e:
            log.warning("Falha ao obter infos do vídeo %s: %s", video.id, e)
            continue
        video.meta_dados = meta
        video.titulo_video = (meta.get("titulo") or "")[:255] or None
        db.session.commit()

    return len(pendentes)


def mudar_status(video_id: int, de: str, para: str, **campos) -> bool:
    """Troca o status só se ele ainda for `de` (evita sobrescrever um cancelamento
    feito pela interface ao mesmo tempo). Retorna True se a troca aconteceu."""
    resultado = db.session.execute(
        update(VideosDownload)
        .where(VideosDownload.id == video_id, VideosDownload.status_download == de)
        .values(status_download=para, **campos)
        .execution_options(synchronize_session=False)
    )
    db.session.commit()
    return resultado.rowcount == 1


def cancelamento_pedido(video_id: int) -> bool:
    # Conexão própria: lê o valor gravado pela interface sem manter transação aberta
    with db.engine.connect() as conn:
        status = conn.execute(
            select(VideosDownload.status_download).where(VideosDownload.id == video_id)
        ).scalar()
    return status == Status.CANCELANDO


def processar_proximo():
    """Baixa o vídeo mais antigo da fila. Retorna False se a fila estiver vazia."""
    video = (
        VideosDownload.query.filter_by(status_download=Status.FILA)
        .order_by(VideosDownload.id)
        .first()
    )
    if not video:
        return False

    video_id, url, titulo_atual = video.id, video.url_video, video.titulo_video
    if not mudar_status(video_id, Status.FILA, Status.BAIXANDO, erro=None):
        return True  # cancelado antes de começar; segue para o próximo
    log.info("Baixando vídeo %s (%s)", video_id, url)

    try:
        caminho, meta = _downloader().baixar(
            url, deve_cancelar=lambda: cancelamento_pedido(video_id)
        )
    except DownloadCancelado:
        mudar_status(video_id, Status.CANCELANDO, Status.CANCELADO, arquivo=None)
        log.info("Download do vídeo %s cancelado", video_id)
        return True
    except Exception as e:
        if not mudar_status(video_id, Status.BAIXANDO, Status.ERRO, erro=str(e)[-2000:]):
            mudar_status(video_id, Status.CANCELANDO, Status.CANCELADO)
        log.error("Falha ao baixar vídeo %s: %s", video_id, e)
        return True

    titulo = (meta.get("titulo") or titulo_atual or "")[:255] or None
    if not mudar_status(video_id, Status.BAIXANDO, Status.CONCLUIDO,
                        arquivo=caminho.name, meta_dados=meta, titulo_video=titulo):
        # Cancelado depois da última verificação: descarta o arquivo pronto
        caminho.unlink(missing_ok=True)
        mudar_status(video_id, Status.CANCELANDO, Status.CANCELADO, arquivo=None)
        log.info("Download do vídeo %s cancelado ao finalizar", video_id)
        return True

    log.info("Vídeo %s concluído: %s", video_id, caminho.name)
    return True


def recuperar_interrompidos():
    """Corrige vídeos que ficaram em andamento quando o worker foi interrompido."""
    voltaram = VideosDownload.query.filter_by(status_download=Status.BAIXANDO).update(
        {"status_download": Status.FILA}
    )
    VideosDownload.query.filter_by(status_download=Status.CANCELANDO).update(
        {"status_download": Status.CANCELADO}
    )
    db.session.commit()
    return voltaram


def ha_pendentes() -> bool:
    return VideosDownload.query.filter_by(status_download=Status.FILA).first() is not None


def executar_worker(intervalo: int, uma_vez: bool = False, ocioso: int | None = None):
    """Processa a fila. Retorna False se outro worker já estiver em execução.

    uma_vez: processa o que está na fila e encerra.
    ocioso: encerra depois de `ocioso` segundos sem nada para baixar (modo usado
    quando o servidor inicia o worker sob demanda). Sem ele, roda para sempre.
    """
    trava = TravaWorker(caminho_trava())
    if not trava.adquirir():
        log.info("Já existe um worker em execução; encerrando.")
        return False

    try:
        # Seguro só com a trava: nenhum outro worker está baixando agora
        n = recuperar_interrompidos()
        if n:
            log.info("%s vídeo(s) interrompido(s) voltaram para a fila", n)

        ultima_atividade = time.monotonic()
        while True:
            atualizar_infos()
            while processar_proximo():
                atualizar_infos()
                ultima_atividade = time.monotonic()

            if uma_vez:
                break

            if ocioso is not None and time.monotonic() - ultima_atividade >= ocioso:
                # Libera a trava antes da última checagem: um link adicionado agora é
                # visto aqui ou faz o servidor iniciar um novo worker (nunca se perde)
                trava.liberar()
                if not ha_pendentes() or not trava.adquirir():
                    break
                ultima_atividade = time.monotonic()
                continue

            time.sleep(intervalo)
    finally:
        trava.liberar()

    log.info("Worker encerrado.")
    return True
