import os
from pathlib import Path

from dotenv import load_dotenv

PATH_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PATH_ROOT.joinpath(".env"))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # Caminho relativo do SQLite é resolvido pelo Flask-SQLAlchemy dentro de instance/
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///aplicativo.db")
    PATH_DOWNLOADS = Path(os.getenv("PATH_DOWNLOADS", PATH_ROOT.joinpath("downloads")))
    # Caminho do ffmpeg (opcional; se vazio, procura no PATH)
    FFMPEG_LOCATION = os.getenv("FFMPEG_LOCATION") or None
    # Intervalo (segundos) entre verificações da fila pelo worker
    WORKER_INTERVALO = int(os.getenv("WORKER_INTERVALO", "10"))
    # Inicia o worker automaticamente quando um link é adicionado pela interface
    WORKER_AUTO_START = os.getenv("WORKER_AUTO_START", "1").lower() not in ("0", "false", "nao", "não")
    # Segundos sem nada para baixar até o worker iniciado pelo servidor encerrar
    WORKER_OCIOSO = int(os.getenv("WORKER_OCIOSO", "30"))
