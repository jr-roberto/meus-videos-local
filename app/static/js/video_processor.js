(() => {
    'use strict';

    // ── Configuração ────────────────────────────────────────────
    const ENDPOINT = '/api/process-video';
    const LIST_ENDPOINT = '/api/videos'; // GET lista, DELETE /:id, POST /:id/reprocess, GET /:id/arquivo
    const POLL_MS = 5000; // atualização automática enquanto há vídeos pendentes

    // ── Elementos ───────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);
    const form = $('form'), field = $('field'), input = $('url');
    const submitBtn = $('submit'), label = $('label'), spinner = $('spinner');
    const pasteBtn = $('paste'), clearBtn = $('clear');
    const errBox = $('error'), errText = $('error-text');
    const okBox = $('ok'), okText = $('ok-text');

    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // ── Tema ────────────────────────────────────────────────────
    const themeBtn = $('themeToggle');
    function updateThemeButton() {
        themeBtn.textContent = document.documentElement.dataset.theme === 'dark' ? '☀️ Tema claro' : '🌙 Tema escuro';
    }
    themeBtn.addEventListener('click', () => {
        const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem('theme', next); } catch { }
        updateThemeButton();
    });
    updateThemeButton();

    // ── Validação ───────────────────────────────────────────────
    const ID_RE = /^[A-Za-z0-9_-]{11}$/;
    const HOSTS = new Set(['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com']);

    /** Retorna { ok, id, url } ou { ok:false, reason } */
    function parseYouTube(raw) {
        const value = raw.trim();
        if (!value) return { ok: false, reason: 'empty' };

        let u;
        try { u = new URL(/^https?:\/\//i.test(value) ? value : 'https://' + value); }
        catch { return { ok: false, reason: 'format' }; }
        if (!u.hostname.includes('.')) return { ok: false, reason: 'format' };

        const host = u.hostname.toLowerCase();
        let id = null;

        if (host === 'youtu.be') {
            id = u.pathname.split('/')[1];
        } else if (HOSTS.has(host)) {
            const parts = u.pathname.split('/').filter(Boolean);
            if (u.pathname === '/watch') id = u.searchParams.get('v');
            else if (['shorts', 'embed', 'live', 'v'].includes(parts[0])) id = parts[1];
        } else {
            return { ok: false, reason: 'host' };
        }

        if (!id || !ID_RE.test(id)) return { ok: false, reason: 'id' };
        return { ok: true, id, url: 'https://www.youtube.com/watch?v=' + id };
    }

    const MESSAGES = {
        empty: 'Cole o link de um vídeo para continuar.',
        format: 'Isso não parece um endereço válido. Confira se copiou o link completo.',
        host: 'Esse link não é do YouTube. Use um endereço como youtube.com/watch?v=… ou youtu.be/….',
        id: 'Não encontramos um vídeo nesse link. Abra o vídeo no YouTube e copie o endereço da barra do navegador.',
    };

    // ── Estados de UI ───────────────────────────────────────────
    let busy = false;

    function show(box, textEl, text) {
        textEl.textContent = text;
        box.hidden = false;
    }
    function clearMessages() { errBox.hidden = true; okBox.hidden = true; }

    function render(showErrors) {
        const result = parseYouTube(input.value);
        clearBtn.hidden = !input.value || busy;
        pasteBtn.hidden = !!input.value || busy;
        submitBtn.disabled = busy || !result.ok;

        field.classList.remove('is-invalid', 'is-valid');
        input.setAttribute('aria-invalid', 'false');
        errBox.hidden = true;

        if (result.ok) {
            field.classList.add('is-valid');
            if (!busy) { okBox.hidden = false; okText.innerHTML = 'Vídeo reconhecido: <code>' + esc(result.id) + '</code>'; }
        } else if (showErrors && input.value.trim()) {
            okBox.hidden = true;
            field.classList.add('is-invalid');
            input.setAttribute('aria-invalid', 'true');
            show(errBox, errText, MESSAGES[result.reason]);
        } else {
            okBox.hidden = true;
        }
        return result;
    }

    function setLoading(on) {
        busy = on;
        input.disabled = on;
        spinner.hidden = !on;
        submitBtn.classList.toggle('is-loading', on);
        submitBtn.setAttribute('aria-busy', String(on));
        if (on) submitBtn.disabled = true;
        label.textContent = on ? 'Enviando…' : 'Adicionar à fila';
    }

    // ── Eventos do formulário ───────────────────────────────────
    let timer;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        render(false);
        // valida em tempo real após uma pausa na digitação
        timer = setTimeout(() => render(true), 600);
    });
    input.addEventListener('blur', () => render(true));

    clearBtn.addEventListener('click', () => {
        input.value = ''; render(false); input.focus();
    });

    pasteBtn.addEventListener('click', async () => {
        try {
            input.value = (await navigator.clipboard.readText()).trim();
        } catch {
            input.focus(); // sem permissão: o usuário cola manualmente
            return;
        }
        render(true); input.focus();
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (busy) return;
        const result = render(true);
        if (!result.ok) { input.focus(); return; }

        setLoading(true);
        clearMessages();
        try {
            const { data, worker } = await sendVideo(result.url);
            upsertVideo(data);
            input.value = '';
            field.classList.remove('is-valid');
            okBox.hidden = false;
            okText.innerHTML = '<strong>Vídeo adicionado à fila.</strong> Pedido <code>#' + esc(data.id) + '</code>. ' +
                esc(WORKER_MSG[worker] || '') + ' <a href="#" data-go="manager">Ver em Gerenciar vídeos</a>';
        } catch (err) {
            field.classList.add('is-invalid');
            show(errBox, errText, err.message || 'Não foi possível enviar agora. Tente novamente em instantes.');
        } finally {
            setLoading(false);
            clearBtn.hidden = !input.value;
            pasteBtn.hidden = !!input.value;
            submitBtn.disabled = !parseYouTube(input.value).ok;
        }
    });

    // ── Comunicação com o servidor ──────────────────────────────
    async function request(method, url, body) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const res = await fetch(url, {
                method,
                headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
                body: body ? JSON.stringify(body) : undefined,
                signal: controller.signal,
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || 'O servidor respondeu com erro ' + res.status + '.');
            return data;
        } catch (err) {
            if (err.name === 'AbortError') throw new Error('O servidor demorou para responder. Tente novamente.');
            if (err instanceof TypeError) throw new Error('Sem conexão com o servidor.');
            throw err;
        } finally {
            clearTimeout(timeout);
        }
    }

    const sendVideo = (url) => request('POST', ENDPOINT, { url });
    const WORKER_MSG = {
        iniciado: 'O download vai começar em instantes.',
        em_execucao: 'O worker já está trabalhando e vai baixá-lo na sequência.',
        falhou: 'Não foi possível iniciar o worker automaticamente; rode python worker.py.',
    };

    // ── Navegação lateral ───────────────────────────────────────
    const views = { form: $('view-form'), manager: $('view-manager') };
    const navBtns = document.querySelectorAll('.nav-btn');
    let currentView = 'form';

    function showView(name) {
        currentView = name;
        for (const k in views) views[k].hidden = k !== name;
        navBtns.forEach((b) => {
            const on = b.dataset.view === name;
            b.classList.toggle('is-active', on);
            if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
        });
        window.scrollTo(0, 0);
        if (name === 'manager') loadVideos();
    }
    navBtns.forEach((b) => b.addEventListener('click', () => showView(b.dataset.view)));
    okBox.addEventListener('click', (e) => {
        if (e.target.closest('[data-go]')) { e.preventDefault(); showView('manager'); }
    });

    // ── Gerenciador de vídeos ───────────────────────────────────
    const STATUS = { FILA: 'Na fila', BAIXANDO: 'Baixando', CANCELANDO: 'Cancelando…', CONCLUIDO: 'Concluído', ERRO: 'Falhou', CANCELADO: 'Cancelado' };
    const PENDING = new Set(['FILA', 'BAIXANDO', 'CANCELANDO']);
    const RETRYABLE = new Set(['ERRO', 'CANCELADO']);

    const ago = (ts) => {
        if (!ts) return '';
        const m = Math.round((Date.now() - ts) / 60000);
        if (m < 1) return 'agora mesmo';
        if (m < 60) return 'há ' + m + ' min';
        const h = Math.round(m / 60);
        return h < 24 ? 'há ' + h + ' h' : 'há ' + Math.round(h / 24) + ' d';
    };
    const duration = (s) => {
        if (!s) return '';
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = String(Math.floor(s % 60)).padStart(2, '0');
        return h ? h + ':' + String(m).padStart(2, '0') + ':' + sec : m + ':' + sec;
    };

    let videos = [];
    let filter = 'all', query = '';
    let pollTimer = null;

    const fromApi = (v) => ({ ...v, at: v.recebidoEm ? new Date(v.recebidoEm).getTime() : null });

    function upsertVideo(data) {
        const v = fromApi(data);
        const i = videos.findIndex((x) => x.id === v.id);
        if (i >= 0) videos[i] = v; else videos.unshift(v);
        renderManager();
    }

    function mgrError(text) { const b = $('mgr-error'); b.textContent = text; b.hidden = false; }

    async function loadVideos({ silent = false } = {}) {
        const btn = $('refresh');
        if (!silent) { $('mgr-error').hidden = true; btn.disabled = true; btn.textContent = 'Atualizando…'; }
        try {
            videos = (await request('GET', LIST_ENDPOINT)).map(fromApi);
        } catch (err) {
            if (!silent) mgrError('Não foi possível carregar os vídeos. ' + err.message);
        } finally {
            if (!silent) { btn.disabled = false; btn.textContent = 'Atualizar'; }
        }
        renderManager();
    }

    function schedulePoll() {
        clearTimeout(pollTimer);
        if (currentView === 'manager' && videos.some((v) => PENDING.has(v.status))) {
            pollTimer = setTimeout(() => loadVideos({ silent: true }), POLL_MS);
        }
    }

    function renderItem(v) {
        const title = v.titulo || 'Aguardando informações do vídeo…';
        const meta = [v.canal, duration(v.duracao), 'Pedido #' + v.id, 'recebido ' + ago(v.at)].filter(Boolean).join(' · ');
        const playable = v.status === 'CONCLUIDO' && v.temArquivo;
        return '<li class="item" data-id="' + esc(v.id) + '">' +
            '<div class="thumb" aria-hidden="true">' +
            (v.videoId ? '<img src="https://i.ytimg.com/vi/' + encodeURIComponent(v.videoId) + '/mqdefault.jpg" alt="" loading="lazy">' : '') +
            '</div>' +
            '<div style="min-width:0"><div class="item-title" title="' + esc(title) + '">' + esc(title) + '</div>' +
            '<div class="item-meta">' + esc(meta) + '</div>' +
            (v.status === 'ERRO' && v.erro ? '<div class="item-error" title="' + esc(v.erro) + '">' + esc(v.erro) + '</div>' : '') +
            '</div>' +
            '<span class="badge ' + esc(v.status) + '">' + esc(STATUS[v.status] || v.status) + '</span>' +
            '<div class="actions">' +
            (playable ? '<button type="button" class="act primary" data-action="play">Assistir</button>' : '') +
            '<a class="act" href="' + esc(v.url) + '" target="_blank" rel="noopener noreferrer">YouTube</a>' +
            (v.status === 'FILA' || v.status === 'BAIXANDO' ? '<button type="button" class="act danger" data-action="cancel">Cancelar</button>' : '') +
            (RETRYABLE.has(v.status) ? '<button type="button" class="act" data-action="retry">' + (v.status === 'ERRO' ? 'Tentar de novo' : 'Baixar de novo') + '</button>' : '') +
            (v.status !== 'BAIXANDO' && v.status !== 'CANCELANDO' ? '<button type="button" class="act danger" data-action="remove">Remover</button>' : '') +
            '</div>' +
            '</li>';
    }

    function renderManager() {
        const counts = { all: videos.length, FILA: 0, BAIXANDO: 0, CONCLUIDO: 0, ERRO: 0, CANCELADO: 0 };
        videos.forEach((v) => { if (v.status in counts) counts[v.status]++; });
        document.querySelectorAll('.chip').forEach((c) => {
            c.setAttribute('aria-pressed', String(c.dataset.filter === filter));
            c.querySelector('span').textContent = counts[c.dataset.filter];
        });
        $('nav-count').textContent = videos.length;
        $('mgr-sub').textContent = videos.length + (videos.length === 1 ? ' vídeo na biblioteca.' : ' vídeos na biblioteca.');

        const q = query.trim().toLowerCase();
        const rows = videos.filter((v) => (filter === 'all' || v.status === filter) &&
            (!q || [v.titulo, v.canal, v.videoId, String(v.id)].some((s) => s && s.toLowerCase().includes(q))));
        const list = $('list');

        list.innerHTML = rows.length ? rows.map(renderItem).join('') :
            '<li class="empty">' + (videos.length
                ? '<p>Nenhum vídeo corresponde a esse filtro.</p>'
                : '<p>Nenhum vídeo recebido ainda.</p><button type="button" class="ghost" data-action="go-form">Enviar um link</button>') + '</li>';

        schedulePoll();
    }

    $('list').addEventListener('click', async (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;

        const action = btn.dataset.action;
        if (action === 'go-form') { showView('form'); return; }

        const id = Number(btn.closest('.item').dataset.id);
        const v = videos.find((x) => x.id === id);
        if (!v) return;

        $('mgr-error').hidden = true;

        if (action === 'play') {
            openPlayer(v);
            return;
        }

        if ((action === 'remove' || action === 'cancel') && !btn.classList.contains('armed')) { // 1º clique pede confirmação
            const original = btn.textContent;
            btn.classList.add('armed'); btn.textContent = action === 'remove' ? 'Confirmar remoção' : 'Confirmar cancelamento';
            setTimeout(() => { if (btn.isConnected) { btn.classList.remove('armed'); btn.textContent = original; } }, 3000);
            return;
        }

        if (action === 'remove') {
            btn.disabled = true;
            try {
                await request('DELETE', LIST_ENDPOINT + '/' + id);
                videos = videos.filter((x) => x.id !== id);
            } catch (err) { mgrError('Não foi possível remover o vídeo. ' + err.message); }
        } else if (action === 'cancel') {
            btn.disabled = true;
            try {
                const { data } = await request('POST', LIST_ENDPOINT + '/' + id + '/cancel');
                Object.assign(v, fromApi(data));
            } catch (err) { mgrError('Não foi possível cancelar o download. ' + err.message); }
        } else if (action === 'retry') {
            btn.disabled = true;
            try {
                const { data } = await request('POST', LIST_ENDPOINT + '/' + id + '/reprocess');
                Object.assign(v, fromApi(data));
            } catch (err) { mgrError('Não foi possível reenviar o vídeo. ' + err.message); }
        }
        renderManager();
    });

    $('chips').addEventListener('click', (e) => {
        const c = e.target.closest('.chip');
        if (c) { filter = c.dataset.filter; renderManager(); }
    });
    $('search').addEventListener('input', (e) => { query = e.target.value; renderManager(); });
    $('refresh').addEventListener('click', () => loadVideos());

    // ── Player ──────────────────────────────────────────────────
    const player = $('player'), playerVideo = $('player-video');

    function openPlayer(v) {
        $('player-title').textContent = v.titulo || 'Vídeo #' + v.id;
        playerVideo.src = LIST_ENDPOINT + '/' + v.id + '/arquivo';
        player.showModal();
        playerVideo.play().catch(() => { });
    }
    $('player-close').addEventListener('click', () => player.close());
    player.addEventListener('click', (e) => { if (e.target === player) player.close(); });
    player.addEventListener('close', () => { playerVideo.pause(); playerVideo.removeAttribute('src'); playerVideo.load(); });

    render(false);
    loadVideos({ silent: true }); // preenche o contador da navegação
})();
