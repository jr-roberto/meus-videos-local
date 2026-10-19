from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import Column
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()

class VideosDownload(db.Model):
    __tablename__ = "videos_download"

    id = Column(db.Integer, primary_key=True)
    titulo_video = Column(db.String(255), nullable=True)
    url_video = Column(db.String(100), nullable=True, unique=True)
    status_download = Column(db.String(45), default="FILA")
    data_registro = Column(db.DateTime, default=datetime.now)
    meta_dados = Column(db.JSON, nullable=True)
    
    