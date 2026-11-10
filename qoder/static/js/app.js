let currentSession = null;
let isProcessing = false;

const API = {
    async get(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(r.status);
        return r.json();
    },
    async post(url, body) {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
        if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
        return r.json();
    },
};

document.addEventListener('DOMContentLoaded', () => { checkStatus(); setInterval(checkStatus, 30000); });

async function checkStatus() {
    try {
        const d = await API.get('/api/status');
        const dot = document.getElementById('pc-status');
        const txt = document.getElementById('pc-status-text');
        dot.className = 'status-dot ' + (d.powercontext === 'connected' ? 'online' : 'offline');
        txt.textContent = d.powercontext === 'connected' ? 'PowerContext 已连接 (seekdb)' : 'PowerContext 离线 (本地模式)';
    } catch { document.getElementById('pc-status-text').textContent = '服务未启动'; }
}

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

async function startGame() {
    const btn = document.getElementById('btn-start');
    btn.disabled = true; btn.textContent = '命运之轮转动中...';
    try {
        const data = await API.post('/api/game/start', {
            name: document.getElementById('char-name').value.trim(),
            gender: document.getElementById('char-gender').value,
            background: document.getElementById('char-bg').value,
        });
        currentSession = data;
        showScreen('game-screen');
        renderCharacter(data.character);
        renderActions(data.available_actions || []);
        renderOpening(data);
        document.getElementById('turn-counter').textContent = `第 ${data.turn_count} 回合`;
    } catch (e) { alert('启动失败: ' + e.message); }
    finally { btn.disabled = false; btn.textContent = '开始新人生'; }
}

function renderOpening(data) {
    const area = document.getElementById('narrative-area');
    area.innerHTML = '';
    const log = data.action_log || [];
    if (log.length > 0) {
        appendMsg('system', `${data.character.name} 出生了 — ${data.character.birth_city}，${data.character.family_background}`);
    }
}

async function performAction(actionId) {
    if (isProcessing || !currentSession) return;
    isProcessing = true;
    const card = document.querySelector(`[data-action="${actionId}"]`);
    const actionName = card ? card.querySelector('.ac-name').textContent : actionId;
    appendMsg('player', actionName);
    showLoading();

    try {
        const data = await API.post(`/api/game/${currentSession.session_id}/action`, { action_id: actionId });
        currentSession = { ...currentSession, character: data.character, turn_count: data.turn_count, is_active: data.is_active };
        renderCharacter(data.character);
        renderActions(data.available_actions || []);
        renderActionResult(data.result);
        document.getElementById('turn-counter').textContent = `第 ${data.turn_count} 回合`;
        if (data.result.is_game_over) setTimeout(() => showGameOver(data.result, data.character), 2500);
    } catch (e) {
        appendMsg('system', '行动失败: ' + e.message);
        renderActions(currentSession.available_actions || []);
    } finally { isProcessing = false; removeLoading(); }
}

function renderCharacter(char) {
    document.getElementById('char-name-display').textContent = char.name;
    document.getElementById('char-occupation').textContent = `${char.life_stage_label} · ${char.occupation}`;
    document.getElementById('char-age-badge').textContent = `${char.age}岁`;

    updateVital('health', char.vitals.health);
    updateVital('happiness', char.vitals.happiness);
    updateVital('energy', char.vitals.energy);

    renderAbilities(char.abilities, char.ability_categories);

    const skillsSec = document.getElementById('skills-section');
    const skillsList = document.getElementById('skills-list');
    if (char.skills && char.skills.length > 0) {
        skillsSec.style.display = 'block';
        skillsList.innerHTML = char.skills.map(s => `<span class="tag">${s}</span>`).join('');
    } else { skillsSec.style.display = 'none'; }

    const relsSec = document.getElementById('relations-section');
    const relsList = document.getElementById('relations-list');
    if (char.relationships && char.relationships.length > 0) {
        relsSec.style.display = 'block';
        relsList.innerHTML = char.relationships.map(r => `<span class="tag">${r.name} · ${r.type}</span>`).join('');
    } else { relsSec.style.display = 'none'; }
}

function updateVital(name, value) {
    const bar = document.getElementById(`bar-${name}`);
    const val = document.getElementById(`val-${name}`);
    if (bar) bar.style.width = `${value}%`;
    if (val) val.textContent = value;
}

function renderAbilities(abilities, categories) {
    const container = document.getElementById('ability-categories');
    if (!categories) return;
    let html = '';
    for (const [catKey, catInfo] of Object.entries(categories)) {
        html += `<div class="ability-cat"><div class="ability-cat-label">${catInfo.label}</div><div class="ability-grid">`;
        for (const key of catInfo.keys) {
            const ab = abilities[key];
            if (!ab) continue;
            html += `<div class="ability-cell">
                <span class="ab-name">${ab.label}</span>
                <span><span class="ab-val" style="color:${ab.color}">${ab.value}</span><span class="ab-rank" style="color:${ab.color}">${ab.rank}</span></span>
            </div>`;
        }
        html += '</div></div>';
    }
    container.innerHTML = html;
}

function renderActions(actions) {
    const container = document.getElementById('action-cards');
    if (!actions || actions.length === 0) { container.innerHTML = ''; return; }
    const energy = currentSession?.character?.vitals?.energy || 100;
    container.innerHTML = actions.map(a => {
        const disabled = a.energy_cost > 0 && energy < a.energy_cost;
        const effectsHtml = a.effects.map(e => `<span class="ac-effect">${e.label}+${e.amount}</span>`).join('');
        const costLabel = a.energy_cost > 0 ? `⚡${a.energy_cost}` : `⚡+${Math.abs(a.energy_cost)}`;
        return `<div class="action-card ${disabled ? 'disabled' : ''}" data-action="${a.id}" onclick="performAction('${a.id}')">
            <div class="ac-cost">${costLabel}</div>
            <div class="ac-icon">${a.icon}</div>
            <div class="ac-name">${a.name}</div>
            <div class="ac-desc">${a.description}</div>
            <div class="ac-effects">${effectsHtml}${a.months_advance ? `<span class="ac-effect" style="background:rgba(243,156,18,0.15);color:var(--energy)">+${a.months_advance}月</span>` : ''}</div>
        </div>`;
    }).join('');
}

function renderActionResult(result) {
    let html = result.narrative;
    const changes = [];
    for (const [k, v] of Object.entries(result.ability_changes || {})) {
        if (v === 0) continue;
        changes.push(`<span class="${v > 0 ? 'up' : 'down'}">${k}${v > 0 ? '+' : ''}${v}</span>`);
    }
    for (const [k, v] of Object.entries(result.vitality_changes || {})) {
        if (v === 0) continue;
        const label = { health: '健康', happiness: '幸福' }[k] || k;
        changes.push(`<span class="${v > 0 ? 'up' : 'down'}">${label}${v > 0 ? '+' : ''}${v}</span>`);
    }
    if (result.energy_change) changes.push(`<span class="neutral">精力${result.energy_change > 0 ? '+' : ''}${result.energy_change}</span>`);
    if (changes.length) html += `<div class="result-stats">${changes.join(' ')}</div>`;
    if (result.life_lesson) html += `<div class="lesson-text">💡 ${result.life_lesson}</div>`;
    if (result.special_event) html += `<div class="event-text">⭐ ${result.special_event}</div>`;
    if (result.new_skill) html += `<div class="event-text">🔧 习得技能: ${result.new_skill}</div>`;
    appendMsg('narrator', html, true);
}

function appendMsg(role, content, isHtml = false) {
    const area = document.getElementById('narrative-area');
    const div = document.createElement('div');
    div.className = `narrative-msg ${role}`;
    if (isHtml) div.innerHTML = content; else div.textContent = content;
    area.appendChild(div);
    area.scrollTop = area.scrollHeight;
}

function showLoading() {
    const cards = document.getElementById('action-cards');
    cards.innerHTML = '<div style="display:flex;align-items:center;gap:0.5rem;padding:1rem;color:var(--text-muted)"><div class="loading"></div><span>行动中...</span></div>';
}

function removeLoading() { }

async function saveGame() {
    if (!currentSession) return;
    try {
        const d = await API.post(`/api/game/${currentSession.session_id}/save`);
        appendMsg('system', d.success ? `存档成功!` : d.message);
    } catch (e) { appendMsg('system', '存档失败: ' + e.message); }
}

async function toggleTimeline() {
    if (!currentSession) return;
    const panel = document.getElementById('timeline-panel');
    const layout = document.querySelector('.game-layout');
    if (panel.style.display === 'none') {
        panel.style.display = 'flex';
        layout.classList.add('timeline-open');
        try {
            const d = await API.get(`/api/game/${currentSession.session_id}/timeline`);
            renderTimeline(d.timeline);
            renderExperiences(d.experiences);
        } catch { document.getElementById('timeline-list').innerHTML = '<p style="color:var(--text-muted)">无法加载</p>'; }
    } else { panel.style.display = 'none'; layout.classList.remove('timeline-open'); }
}

function renderTimeline(entries) {
    const list = document.getElementById('timeline-list');
    if (!entries || entries.length === 0) { list.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem">暂无记忆</p>'; return; }
    list.innerHTML = entries.map(e => `<div class="timeline-item"><div class="tl-age">${e.age || '?'}岁 <span class="tl-kind">${e.kind || ''}</span></div><div>${e.text || ''}</div></div>`).join('');
}

function renderExperiences(entries) {
    const sec = document.getElementById('experiences-section');
    const list = document.getElementById('experiences-list');
    if (!entries || entries.length === 0) { sec.style.display = 'none'; return; }
    sec.style.display = 'block';
    list.innerHTML = entries.map(e => `<div class="experience-item"><div><b>情境:</b> ${e.situation}</div><div><b>行动:</b> ${e.action}</div><div class="exp-lesson">教训: ${e.lesson}</div></div>`).join('');
}

function showGameOver(result, char) {
    showScreen('gameover-screen');
    document.getElementById('gameover-text').textContent = result.game_over_text || result.narrative;
    const abHtml = Object.entries(char.abilities || {}).map(([k, v]) => {
        const info = typeof v === 'object' ? v : { value: v, rank: '?', color: '#999', label: k };
        return `<div class="go-ability"><div class="go-label">${info.label}</div><div class="go-value" style="color:${info.color}">${info.value}</div><div class="go-rank" style="color:${info.color}">${info.rank}</div></div>`;
    }).join('');
    document.getElementById('gameover-abilities').innerHTML = abHtml;
}

function resetGame() { currentSession = null; showScreen('start-screen'); document.getElementById('narrative-area').innerHTML = ''; document.getElementById('action-cards').innerHTML = ''; }
