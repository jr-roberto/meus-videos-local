
import yt_dlp
from pathlib import Path

class RobotYouTube():
    def __init__(self, url:str, download_path:Path):
        self.url = url
        self.download_path = download_path
        pass

    def download_video(self):

        opcoes = {
            "format": "bestvideo*+bestaudio/best",
            "outtmpl": str(self.download_path.joinpath("%(title)s.%(ext)s")),
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(opcoes) as downloader:
                downloader.download([self.url])

            print("Download concluído!", Path(opcoes["outtmpl"]).name)

        except Exception as erro:
            print(f"Erro ao baixar o vídeo: {erro}")


        return 


    def get_infos(self):
        info_json = None

        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:

            info = ydl.extract_info(self.url, download=False)
            info_json = ydl.sanitize_info(info)

        return info_json

    def get_info2(self):
        info = None

        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(self.url, download=False)

            info = {
                "Título": info.get("title"),
                "Canal": info.get("uploader"),
                "Duração": info.get("duration"),
                "URL": info.get("webpage_url"),
            }

        return info
