"""Controle do processo do worker: garante uma única instância e permite que o
servidor web o inicie sob demanda."""
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from flask import current_app

from app.config import PATH_ROOT

log = logging.getLogger(__name__)

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class TravaWorker:
    """Trava exclusiva do sistema operacional mantida pelo worker enquanto ele roda.

    É liberada automaticamente se o processo morrer, então não sobra trava "presa"
    como aconteceria com um arquivo de PID.
    """

    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self._arquivo = None

    def adquirir(self) -> bool:
        if self._arquivo:
            return True
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        arquivo = open(self.caminho, "a+")
        try:
            if os.name == "nt":
                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            arquivo.close()
            return False
        self._arquivo = arquivo
        return True

    def liberar(self):
        if not self._arquivo:
            return
        try:
            if os.name == "nt":
                self._arquivo.seek(0)
                msvcrt.locking(self._arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._arquivo.fileno(), fcntl.LOCK_UN)
        finally:
            self._arquivo.close()
            self._arquivo = None


def caminho_trava() -> Path:
    return Path(current_app.instance_path).joinpath("worker.lock")


_lock_inicio = threading.Lock()
_ultimo_processo: subprocess.Popen | None = None


def worker_em_execucao() -> bool:
    # O processo recém-iniciado por este servidor leva ~1 s para pegar a trava;
    # nesse intervalo é ele que conta como "em execução"
    if _ultimo_processo and _ultimo_processo.poll() is None:
        return True
    trava = TravaWorker(caminho_trava())
    if trava.adquirir():
        trava.liberar()
        return False
    return True


def garantir_worker() -> str:
    """Inicia o worker em segundo plano se ele não estiver rodando.

    Retorna "iniciado", "em_execucao" ou "desativado".
    """
    if not current_app.config["WORKER_AUTO_START"]:
        return "desativado"

    with _lock_inicio:
        if worker_em_execucao():
            return "em_execucao"
        _iniciar_processo()
    return "iniciado"


def _iniciar_processo():
    global _ultimo_processo
    # Mesmo que outro servidor inicie um worker ao mesmo tempo, só um consegue a
    # trava; o outro encerra sozinho.
    comando = [sys.executable, str(PATH_ROOT.joinpath("worker.py")), "--ate-esvaziar"]
    opcoes = {}
    if os.name == "nt":
        # Console próprio e oculto (herdado pelo ffmpeg, sem janelas piscando) e
        # grupo separado: um Ctrl+C no terminal do servidor não derruba o worker
        opcoes["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        opcoes["start_new_session"] = True

    caminho_log = Path(current_app.instance_path).joinpath("worker.log")
    with open(caminho_log, "a", encoding="utf-8") as saida:
        _ultimo_processo = subprocess.Popen(
            comando,
            cwd=PATH_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=saida,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            close_fds=True,
            **opcoes,
        )
    log.info("Worker iniciado em segundo plano (log: %s)", caminho_log)
