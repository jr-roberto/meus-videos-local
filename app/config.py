import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

PATH_ROOT = Path(os.getcwd())
PATH_DOWNLOADS = PATH_ROOT.joinpath("downloads")

for pasta in [
    PATH_DOWNLOADS
]:
    if not pasta.exists():
        pasta.mkdir()

class Config():
    PATH_DOWNLOADS = PATH_DOWNLOADS
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SECRET_KEY = os.getenv("SECRET_KEY")
    pass
