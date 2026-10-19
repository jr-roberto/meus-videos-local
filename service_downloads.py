from robots.download_youtube import RobotYouTube
from app import create_app
from app.model import db, VideosDownload
import traceback
from sqlalchemy import desc
app = create_app()

def main():
    with app.app_context():
        fila = VideosDownload.query.filter_by(status_download="FILA").order_by(desc(VideosDownload.id)).first()
        
        if fila:
            download_video(fila.url_video, fila)
            fila.status_download = "CONCLUIDO"

        db.session.commit()

def download_video(url:str, fila):
    fila.status_download = "BAIXANDO"
    db.session.commit()

    try:
        robot = RobotYouTube(
            url=url,
            download_path=app.config["PATH_DOWNLOADS"]
        )
        robot.download_video()
    
    except:
        traceback.print_exc()

        fila.status_download = "ERRO DOWNLOAD"
        db.session.commit()

if __name__=="__main__":
    main()

