from robots.download_youtube import RobotYouTube
from app import create_app
from app.model import db, VideosDownload
import traceback
app = create_app()

def main():
    with app.app_context():
        fila = VideosDownload.query.filter_by(status_download="FILA").all()
        for i in fila:
            meta_dados = get_infos(i)

            if meta_dados:
                i.meta_dados = meta_dados
                i.titulo_video = meta_dados["Título"]
            
            pass

        db.session.commit()

def get_infos(d):
    a = RobotYouTube(d.url_video, "")
    return a.get_info2()


if __name__=="__main__":
    main()

