import logging

import click
from flask import current_app
from flask.cli import AppGroup

from app.services import fila
from app.services.processo_worker import TravaWorker, caminho_trava

fila_cli = AppGroup("fila", help="Gerencia a fila de downloads.")


def _configurar_log():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@fila_cli.command("infos")
def infos():
    """Busca título e metadados dos vídeos na fila."""
    _configurar_log()
    click.echo(f"{fila.atualizar_infos()} vídeo(s) verificados.")


@fila_cli.command("baixar")
def baixar():
    """Baixa o próximo vídeo da fila."""
    _configurar_log()
    trava = TravaWorker(caminho_trava())
    if not trava.adquirir():
        click.echo("Já existe um worker em execução.")
        return
    try:
        if not fila.processar_proximo():
            click.echo("Fila vazia.")
    finally:
        trava.liberar()


@fila_cli.command("worker")
@click.option("--intervalo", type=int, default=None, help="Segundos entre verificações da fila.")
@click.option("--uma-vez", is_flag=True, help="Processa a fila atual e encerra.")
@click.option("--ate-esvaziar", is_flag=True, help="Encerra após WORKER_OCIOSO segundos sem trabalho.")
def worker(intervalo, uma_vez, ate_esvaziar):
    """Processa a fila continuamente (infos + downloads)."""
    _configurar_log()
    fila.executar_worker(
        intervalo or current_app.config["WORKER_INTERVALO"],
        uma_vez=uma_vez,
        ocioso=current_app.config["WORKER_OCIOSO"] if ate_esvaziar else None,
    )
