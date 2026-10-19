# meus-videos-local
Biblioteca de vídeos do YouTube para assistir localmente.

Você cola o link na interface web, o vídeo entra numa fila e um worker o baixa com o
[yt-dlp](https://github.com/yt-dlp/yt-dlp). Depois é só assistir no próprio navegador.

## Requisitos

- Python 3.11+
- **ffmpeg** — necessário para juntar vídeo e áudio (o YouTube entrega separados):
  `winget install Gyan.FFmpeg`, ou indique o caminho em `FFMPEG_LOCATION` no `.env`
- Node.js ou Deno — o yt-dlp usa um runtime JavaScript para extrair do YouTube

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask db upgrade
```

## Uso

```bash
python wsgi.py        # interface web em http://localhost:8080
```

Basta o servidor: sempre que um link é adicionado (ou um vídeo é reenviado), ele inicia o
worker em segundo plano. Se o worker já estiver rodando, o pedido é ignorado e o vídeo
entra na fila dele. O worker iniciado assim encerra sozinho depois de `WORKER_OCIOSO`
segundos sem nada para baixar. A saída fica em `instance/worker.log`.

Para desligar esse comportamento, use `WORKER_AUTO_START=0` no `.env` e rode o worker à mão:

```bash
python worker.py                 # loop contínuo
python worker.py --ate-esvaziar  # encerra quando a fila esvaziar
python worker.py --uma-vez       # processa a fila atual e encerra
```

Comandos da fila (equivalentes, via Flask CLI):

```bash
flask fila worker            # loop contínuo (--intervalo N, --uma-vez, --ate-esvaziar)
flask fila infos             # só busca título/metadados dos vídeos na fila
flask fila baixar            # baixa apenas o próximo vídeo
```

Só um worker roda por vez: ele mantém uma trava em `instance/worker.lock` (liberada
automaticamente se o processo morrer), e uma segunda instância encerra na hora.
Se o worker for interrompido no meio de um download, o vídeo volta para a fila na próxima execução.

## Estrutura

```
app/
  __init__.py        create_app (blueprints, extensões, CLI)
  config.py          configuração via .env
  extensions.py      db / migrate
  models.py          VideosDownload + Status
  cli.py             comandos "flask fila ..."
  services/
    youtube.py       validação de links e integração com yt-dlp
    fila.py          processamento da fila e localização de arquivos
    processo_worker.py  trava de instância única e início do worker pelo servidor
  routes/
    api.py           API REST
    web.py           página
  templates/, static/
migrations/          Alembic (Flask-Migrate)
worker.py            entrada do worker
wsgi.py              entrada do servidor web
```

## API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/process-video` | `{"url": "..."}` — adiciona à fila (409 se já existir) |
| GET | `/api/videos` | lista os vídeos (exceto removidos) |
| DELETE | `/api/videos/<id>` | apaga o arquivo e marca como removido |
| POST | `/api/videos/<id>/cancel` | cancela um vídeo na fila ou em download |
| POST | `/api/videos/<id>/reprocess` | devolve um vídeo com falha ou cancelado para a fila |
| GET | `/api/videos/<id>/arquivo` | stream do arquivo baixado (suporta Range) |
| GET | `/api/worker` | `{"emExecucao": true/false}` |

Status: `FILA` → `BAIXANDO` → `CONCLUIDO` ou `ERRO`; `DELETADO` após remover.

### Cancelamento

- Na fila: o vídeo vai direto para `CANCELADO`.
- Em download: fica `CANCELANDO` até o worker perceber (cerca de 1 s), interromper o yt-dlp
  e apagar os arquivos gerados por esse download (`.part`, streams `.fNNN.*`, temporário da
  junção e o arquivo final, se já existir). Depois passa para `CANCELADO`.
- A junção de vídeo e áudio pelo ffmpeg não pode ser interrompida no meio; o cancelamento é
  aplicado logo que ela termina, e o arquivo resultante é apagado.
- Arquivos que já existiam na pasta antes do download nunca são apagados pelo cancelamento.
