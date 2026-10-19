"""Processa a fila de downloads.

Uso: python worker.py [--uma-vez | --ate-esvaziar]
(equivalente a: flask fila worker)

Só uma instância roda por vez; uma segunda execução encerra imediatamente.
O servidor web inicia este script com --ate-esvaziar sempre que um link é adicionado.
"""
import argparse
import logging
import sys

from app import create_app
from app.services.fila import executar_worker

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Processa a fila de downloads.")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--uma-vez", action="store_true", help="processa a fila atual e encerra")
    modo.add_argument("--ate-esvaziar", action="store_true",
                      help="encerra após WORKER_OCIOSO segundos sem nada para baixar")
    args = parser.parse_args()

    # Evita erro de encoding do console do Windows com títulos em Unicode
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="backslashreplace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    app = create_app()
    with app.app_context():
        executar_worker(
            app.config["WORKER_INTERVALO"],
            uma_vez=args.uma_vez,
            ocioso=app.config["WORKER_OCIOSO"] if args.ate_esvaziar else None,
        )
