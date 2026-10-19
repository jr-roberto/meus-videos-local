from flask import (
    Blueprint,
    jsonify,
    request,
    redirect,
    url_for,
    current_app
)

from app.model import db, VideosDownload
from sqlalchemy import desc
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from robots.download_youtube import RobotYouTube
import traceback
from pathlib import Path
import re

u = urlparse("https://www.youtube.com/watch?v=YRqKt-aYPqM")
parse_qs(urlparse("https://www.youtube.com/watch?v=YRqKt-aYPqM").query).get("v", [None])[0]

api = Blueprint(
    name="api",
    import_name=__name__,
    url_prefix="/api"
)

@api.route("/process-video", methods=["POST"])
def process_video():
    try:
        new_video_link = VideosDownload(
            url_video=request.json["url"],
        )

        db.session.add(new_video_link)
        db.session.commit()

        return jsonify({
            "data": {"id": new_video_link.id, "url":new_video_link.url_video}
        })

    except Exception:
        linhas = traceback.format_exc().splitlines()
        erro = "\n".join(linhas[-10:])
        return jsonify({"detail":erro}), 400

@api.route("/videos", methods=["GET"])
@api.route("/videos/<int:id>", methods=["DELETE"])
def videos(id=None):

    if request.method == "GET":
        vds = VideosDownload.query.order_by(desc(VideosDownload.id)).all()

        return [{
            "id":i.id,
            "videoId": parse_qs(urlparse(i.url_video).query).get("v", [None])[0],
            "status": i.status_download,
            "receivedAt":i.data_registro,
            "titulo_video":i.titulo_video
        } for i in vds]

    if request.method == "DELETE":
        vd = VideosDownload.query.get(id)

        titulo = vd.titulo_video

        # Substitui caracteres inválidos por _
        titulo = re.sub(r'[<>:"/\\|?*]', "_", titulo)
        arquivo = current_app.config["PATH_DOWNLOADS"].joinpath(
            f"{titulo}.webm"
        )

        # if arquivo.exists():
        print(arquivo)
        arquivo.unlink(missing_ok=True)

        vd.status_download = "DELETADO"
        db.session.commit()
        
        return jsonify({"ok":"Deletado"})


