(() => {
    'use strict';

    // ── Configuração ────────────────────────────────────────────
    const ENDPOINT = '/api/process-video';
    // true = simula a resposta do servidor (útil sem back-end).
    // Em produção, defina como false para disparar o POST real.
    const SIMULATE = false;

    // ── Elementos ───────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);
    const form = $('form'), field = $('field'), input = $('url');
    const submitBtn = $('submit'), label = $('label'), spinner = $('spinner');
    const pasteBtn = $('paste'), clearBtn = $('clear');
    const errBox = $('error'), errText = $('error-text');
    const okBox = $('ok'), okText = $('ok-text');

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
    let touched = false;
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
        submitBtn.disabled = busy ? false : !result.ok;

        field.classList.remove('is-invalid', 'is-valid');
        input.setAttribute('aria-invalid', 'false');
        errBox.hidden = true;

        if (result.ok) {
            field.classList.add('is-valid');
            if (!busy) { okBox.hidden = false; okText.innerHTML = 'Vídeo reconhecido: <code>' + result.id + '</code>'; }
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
        submitBtn.disabled = on ? true : submitBtn.disabled;
        label.textContent = on ? 'Enviando…' : 'Processar vídeo';
    }

    // ── Eventos ─────────────────────────────────────────────────
    let timer;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        render(false);
        // valida em tempo real após uma pausa na digitação
        timer = setTimeout(() => { touched = true; render(true); }, 600);
    });
    input.addEventListener('blur', () => { touched = true; render(true); });

    clearBtn.addEventListener('click', () => {
        input.value = ''; touched = false; render(false); input.focus();
    });

    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            input.value = text.trim();
        } catch {
            input.focus(); // sem permissão: o usuário cola manualmente
            return;
        }
        touched = true; render(true); input.focus();
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (busy) return;
        touched = true;
        const result = render(true);
        if (!result.ok) { input.focus(); return; }

        setLoading(true);
        clearMessages();
        try {
            const data = await sendVideo(result.url, result.id);
            addVideo(data, result);
            okBox.hidden = false;
            okText.innerHTML = '<strong>Vídeo enviado.</strong> Pedido <code>' + esc(data.jobId) + '</code> recebido. <a href="#" data-go="manager">Ver em Gerenciar vídeos</a>';
            input.disabled = false;
            input.value = ''; touched = false;
            field.classList.remove('is-valid');
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

    // ── Envio ao servidor ───────────────────────────────────────
    async function sendVideo(url, videoId) {
        if (SIMULATE) {
            await new Promise((r) => setTimeout(r, 1600));
            return { jobId: 'job_' + Math.random().toString(36).slice(2, 8), videoId };
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const res = await fetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ url, videoId }),
                signal: controller.signal,
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                throw new Error(
                    data.detail ||
                    data.message ||
                    'O servidor recusou o envio (código ' + res.status + ').'
                );
            }

            return data;

            // if (!res.ok) {
            //     let detail = '';
            //     try { detail = (await res.json()).message || '';} catch { }
            //     throw new Error(res.json().detail || 'O servidor recusou o envio (código ' + res.status + ').');
            // }
            // return await res.json(); // esperado: { jobId: "..." }

        } catch (err) {
            if (err.name === 'AbortError') throw new Error('O servidor demorou para responder. Tente novamente.');
            if (err instanceof TypeError) throw new Error('Sem conexão com o servidor. Verifique sua internet.');
            throw err;
        } finally {
            clearTimeout(timeout);
        }
    }

    // ── Navegação lateral ───────────────────────────────────────
    const LIST_ENDPOINT = '/api/videos'; // GET lista, DELETE /:id, POST /:id/reprocess
    const views = { form: $('view-form'), manager: $('view-manager') };
    const navBtns = document.querySelectorAll('.nav-btn');

    function showView(name) {
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
    const STATUS = { queued: 'Na fila', processing: 'Processando', done: 'Concluído', error: 'Falhou' };
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const ago = (ts) => {
        const m = Math.round((Date.now() - ts) / 60000);
        if (m < 1) return 'agora mesmo';
        if (m < 60) return 'há ' + m + ' min';
        const h = Math.round(m / 60);
        return h < 24 ? 'há ' + h + ' h' : 'há ' + Math.round(h / 24) + ' d';
    };
    const t0 = Date.now();
    let videos = SIMULATE ? [
        { id: 'job_k3m9x1', videoId: 'aB3dE5fG7hI', status: 'done', at: t0 - 5 * 3600e3 },
        { id: 'job_p7q2w8', videoId: 'Zx9Yw8Vu7Ts', status: 'processing', at: t0 - 4 * 60e3 },
        { id: 'job_r5t1n6', videoId: 'Kq1Lm2Np3Rt', status: 'error', at: t0 - 26 * 3600e3 },
    ] : [];
    let filter = 'all', query = '';

    async function api(method, url) {
        const res = await fetch(url, { method, headers: { Accept: 'application/json' } });
        if (!res.ok) throw new Error('O servidor respondeu com erro ' + res.status + '.');
        return res.status === 204 ? null : res.json();
    }
    function mgrError(text) { const b = $('mgr-error'); b.textContent = text; b.hidden = false; }

    function simulateProgress(v) {
        setTimeout(() => { v.status = 'processing'; renderManager(); }, 1500);
        setTimeout(() => { v.status = 'done'; renderManager(); }, 5000);
    }

    function addVideo(data, result) {
        const v = { id: data.jobId || 'job_' + result.id.slice(0, 6), videoId: result.id, status: 'queued', at: Date.now() };
        videos.unshift(v);
        if (SIMULATE) simulateProgress(v);
        renderManager();
    }

    async function loadVideos() {
        $('mgr-error').hidden = true;
        if (!SIMULATE) {
            const btn = $('refresh');
            btn.disabled = true; btn.textContent = 'Atualizando…';
            try {
                const data = await api('GET', LIST_ENDPOINT);
                videos = data.map((v) => ({ id: v.id, videoId: v.videoId, status: v.status, at: new Date(v.receivedAt).getTime(), title: v.titulo_video }));
            } catch (err) {
                mgrError('Não foi possível carregar os vídeos. ' + err.message);
            } finally {
                btn.disabled = false; btn.textContent = 'Atualizar';
            }
        }
        renderManager();
    }

    function renderManager() {
        const counts = { all: videos.length, FILA: 0, BAIXANDO: 0, CONCLUIDO: 0, ERRO: 0 };
        videos.forEach((v) => { if (v.status in counts) counts[v.status]++; });
        document.querySelectorAll('.chip').forEach((c) => {
            c.setAttribute('aria-pressed', String(c.dataset.filter === filter));
            c.querySelector('span').textContent = counts[c.dataset.filter];
        });
        $('nav-count').textContent = videos.length;
        $('mgr-sub').textContent = videos.length + (videos.length === 1 ? ' vídeo recebido' : ' vídeos recebidos') + ' pelo servidor.';

        const q = query.trim().toLowerCase();
        const rows = videos.filter((v) => (filter === 'all' || v.status === filter) &&
            (!q || v.videoId.toLowerCase().includes(q) || v.id.toLowerCase().includes(q)));
        const list = $('list');

        if (!rows.length) {
            list.innerHTML = '<li class="empty">' + (videos.length
                ? '<p>Nenhum vídeo corresponde a esse filtro.</p>'
                : '<p>Nenhum vídeo recebido ainda.</p><button type="button" class="ghost" data-action="go-form">Enviar um link</button>') + '</li>';
            return;
        }
        list.innerHTML = rows.map((v) =>
            '<li class="item" data-id="' + esc(v.id) + '">' +
            '<div class="thumb" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></div>' +
            '<div style="min-width:0"><div class="item-title">Vídeo ' + esc(v.title) + '</div>' +
            '<div class="item-meta">Pedido ' + esc(v.id) + ', recebido ' + ago(v.at) + '</div></div>' +
            '<span class="badge ' + esc(v.status) + '">' + (STATUS[v.status] || esc(v.status)) + '</span>' +
            '<div class="actions">' +
            '<a class="act" href="https://www.youtube.com/watch?v=' + encodeURIComponent(v.videoId) + '" target="_blank" rel="noopener noreferrer">Abrir</a>' +
            (v.status === 'error' ? '<button type="button" class="act" data-action="retry">Tentar de novo</button>' : '') +
            '<button type="button" class="act danger" data-action="remove">Remover</button>' +
            '</div>' +
            '</li>').join('');
    }

    $('list').addEventListener('click', async (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === 'go-form') { showView('form'); return; }
        const id = btn.closest('.item').dataset.id;
        const v = videos.find((x) => x.id === id);
        if (!v) return;
        $('mgr-error').hidden = true;

        if (action === 'remove') {
            if (!btn.classList.contains('armed')) { // 1º clique pede confirmação
                btn.classList.add('armed'); btn.textContent = 'Confirmar remoção';
                setTimeout(() => { if (btn.isConnected) { btn.classList.remove('armed'); btn.textContent = 'Remover'; } }, 3000);
                return;
            }
            btn.disabled = true;
            try {
                if (!SIMULATE) await api('DELETE', LIST_ENDPOINT + '/' + encodeURIComponent(id));
                videos = videos.filter((x) => x.id !== id);
            } catch (err) { mgrError('Não foi possível remover o vídeo. ' + err.message); }
        } else if (action === 'retry') {
            try {
                if (!SIMULATE) await api('POST', LIST_ENDPOINT + '/' + encodeURIComponent(id) + '/reprocess');
                v.status = 'queued';
                if (SIMULATE) simulateProgress(v);
            } catch (err) { mgrError('Não foi possível reenviar o vídeo. ' + err.message); }
        }
        renderManager();
    });

    $('chips').addEventListener('click', (e) => {
        const c = e.target.closest('.chip');
        if (c) { filter = c.dataset.filter; renderManager(); }
    });
    $('search').addEventListener('input', (e) => { query = e.target.value; renderManager(); });
    $('refresh').addEventListener('click', loadVideos);

    render(false);
    renderManager();
})();
