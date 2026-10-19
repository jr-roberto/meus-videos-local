import logging

from flask import Blueprint, abort, jsonify, request, send_file

from app.extensions import db
from app.models import Status, VideosDownload
from app.services.fila import caminho_arquivo, mudar_status
from app.services.processo_worker import garantir_worker, worker_em_execucao
from app.services.youtube import extrair_video_id, normalizar_url

log = logging.getLogger(__name__)

api = Blueprint(
    name="api",
    import_name=__name__,
    url_prefix="/api"
)


def erro(mensagem: str, codigo: int):
    return jsonify({"detail": mensagem}), codigo


def obter_video(id: int) -> VideosDownload:
    video = db.session.get(VideosDownload, id)
    if not video or video.status_download == Status.DELETADO:
        abort(404)
    return video


def acionar_worker() -> str:
    # Falha ao iniciar o worker não deve impedir o vídeo de entrar na fila
    try:
        return garantir_worker()
    except Exception:
        log.exception("Não foi possível iniciar o worker")
        return "falhou"


@api.errorhandler(404)
def nao_encontrado(_):
    return erro("Vídeo não encontrado.", 404)


@api.route("/process-video", methods=["POST"])
def process_video():
    dados = request.get_json(silent=True) or {}
    video_id = extrair_video_id(dados.get("url", ""))
    if not video_id:
        return erro("Link do YouTube inválido.", 400)

    url = normalizar_url(video_id)
    video = VideosDownload.query.filter_by(url_video=url).first()

    if video and video.status_download != Status.DELETADO:
        return erro("Esse vídeo já está na sua lista.", 409)

    if video:
        # Vídeo removido antes: volta para a fila
        video.status_download = Status.FILA
        video.erro = None
        video.arquivo = None
    else:
        video = VideosDownload(url_video=url)
        db.session.add(video)

    db.session.commit()
    return jsonify({"data": video.to_dict(), "worker": acionar_worker()}), 201


@api.route("/videos", methods=["GET"])
def listar_videos():
    videos = (
        VideosDownload.query
        .filter(VideosDownload.status_download != Status.DELETADO)
        .order_by(VideosDownload.id.desc())
        .all()
    )
    return jsonify([v.to_dict() for v in videos])


@api.route("/videos/<int:id>", methods=["DELETE"])
def remover_video(id):
    video = obter_video(id)
    if video.status_download in (Status.BAIXANDO, Status.CANCELANDO):
        return erro("O vídeo está sendo baixado. Cancele o download antes de remover.", 409)

    arquivo = caminho_arquivo(video)
    if arquivo:
        try:
            arquivo.unlink()
        except OSError as e:
            log.exception("Falha ao apagar %s", arquivo)
            return erro(f"Não foi possível apagar o arquivo: {e}", 500)

    video.status_download = Status.DELETADO
    video.arquivo = None
    db.session.commit()
    return jsonify({"ok": True})


@api.route("/videos/<int:id>/cancel", methods=["POST"])
def cancelar_video(id):
    video = obter_video(id)

    # Na fila: cancela na hora. Baixando: o worker interrompe e limpa os arquivos.
    if not (mudar_status(id, Status.FILA, Status.CANCELADO)
            or mudar_status(id, Status.BAIXANDO, Status.CANCELANDO)):
        db.session.refresh(video)
        if video.status_download != Status.CANCELANDO:
            return erro("Só é possível cancelar vídeos na fila ou em download.", 409)

    db.session.refresh(video)
    return jsonify({"data": video.to_dict()})


@api.route("/videos/<int:id>/reprocess", methods=["POST"])
def reprocessar_video(id):
    video = obter_video(id)
    if video.status_download not in (Status.ERRO, Status.CANCELADO):
        return erro("Só é possível reenviar vídeos com falha ou cancelados.", 409)

    video.status_download = Status.FILA
    video.erro = None
    db.session.commit()
    return jsonify({"data": video.to_dict(), "worker": acionar_worker()})


@api.route("/worker", methods=["GET"])
def status_worker():
    return jsonify({"emExecucao": worker_em_execucao()})


@api.route("/videos/<int:id>/arquivo", methods=["GET"])
def arquivo_video(id):
    video = obter_video(id)
    arquivo = caminho_arquivo(video)
    if not arquivo:
        abort(404)
    # conditional=True habilita requisições Range (avançar/voltar no player)
    return send_file(arquivo, conditional=True)
