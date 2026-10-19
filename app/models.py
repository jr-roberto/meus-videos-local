from datetime import datetime

from sqlalchemy import Column

from app.extensions import db
from app.services.youtube import extrair_video_id


class Status:
    FILA = "FILA"
    BAIXANDO = "BAIXANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"
    CANCELANDO = "CANCELANDO"  # pedido feito; o worker ainda vai interromper o download
    CANCELADO = "CANCELADO"
    DELETADO = "DELETADO"


class VideosDownload(db.Model):
    __tablename__ = "videos_download"

    id = Column(db.Integer, primary_key=True)
    titulo_video = Column(db.String(255), nullable=True)
    url_video = Column(db.String(255), nullable=True, unique=True)
    status_download = Column(db.String(45), default=Status.FILA)
    data_registro = Column(db.DateTime, default=datetime.now)
    data_atualizacao = Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    meta_dados = Column(db.JSON, nullable=True)
    # Nome do arquivo final dentro de PATH_DOWNLOADS
    arquivo = Column(db.String(500), nullable=True)
    erro = Column(db.Text, nullable=True)

    @property
    def video_id(self):
        return extrair_video_id(self.url_video or "")

    def to_dict(self):
        meta = self.meta_dados or {}
        return {
            "id": self.id,
            "videoId": self.video_id,
            "url": self.url_video,
            "titulo": self.titulo_video,
            "canal": meta.get("canal"),
            "duracao": meta.get("duracao"),
            "status": self.status_download,
            "erro": self.erro,
            "temArquivo": bool(self.arquivo),
            # ISO sem fuso: o horário é local e o navegador interpreta como local
            "recebidoEm": self.data_registro.isoformat() if self.data_registro else None,
        }
