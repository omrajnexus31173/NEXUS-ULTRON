let activeConversationId = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

function switchScreen(screenId) {
  document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.screen === screenId);
  });
  const target = document.getElementById(`screen-${screenId}`);
  if (target) target.classList.add('active');
  refreshScreen(screenId);
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchScreen(btn.dataset.screen));
});

async function refreshOverview() {
  try {
    const ov = await api('/api/overview');
    const conn = ov.connectivity;
    const tel = ov.telemetry;

    const modeBadge = document.getElementById('badge-mode');
    modeBadge.textContent = `MODE: ${conn.effective_mode.toUpperCase()} (${conn.policy})`;

    document.getElementById('badge-tier').textContent = `${tel.tier_label} | RAM ${tel.ram_percent}%`;

    const shield = document.getElementById('badge-shield');
    if (ov.payment_isolation_locked) {
      shield.textContent = 'PAYMENT LOCKDOWN ENGAGED (USER IN CONTROL)';
      shield.className = 'pill amber';
    } else {
      shield.textContent = 'PAYMENT ISOLATION SHIELD: ARMED';
      shield.className = 'pill green';
    }

    const estopBtn = document.getElementById('btn-emergency');
    estopBtn.textContent = ov.emergency_stop_active ? 'RESUME ULTRON' : 'EMERGENCY STOP';

    const activeTaskLabel = ov.active_task
      ? `${ov.active_task.state}: ${ov.active_task.objective.slice(0, 28)}...`
      : 'Standby (0 Running)';

    document.getElementById('home-metrics').innerHTML = `
      <div class="card"><div class="card-label">ULTRON Availability</div><div class="card-metric">${ov.availability}</div></div>
      <div class="card"><div class="card-label">Hybrid Mode</div><div class="card-metric">${conn.effective_mode.toUpperCase()}</div></div>
      <div class="card"><div class="card-label">Current Task</div><div class="card-metric" style="font-size:15px">${activeTaskLabel}</div></div>
      <div class="card"><div class="card-label">Agents &amp; Queue</div><div class="card-metric">${ov.orchestrator.registered_agent_count} Ready / ${ov.orchestrator.queued_count} Queued</div></div>
      <div class="card"><div class="card-label">CPU Usage</div><div class="card-metric">${tel.cpu_percent}%</div></div>
      <div class="card"><div class="card-label">RAM Usage</div><div class="card-metric">${tel.ram_percent}% (${tel.ram_available_gb} GB Free)</div></div>
      <div class="card"><div class="card-label">Available Storage</div><div class="card-metric">${tel.storage_free_gb} GB</div></div>
      <div class="card"><div class="card-label">Battery / Power</div><div class="card-metric" style="font-size:16px">${tel.battery.status_label}</div></div>
    `;

    const relBox = document.getElementById('home-releases');
    if (ov.releases && ov.releases.length) {
      relBox.innerHTML = ov.releases.map(r =>
        `<div style="padding:6px 0;border-bottom:1px solid #16243B;display:flex;justify-content:space-between;align-items:center;">
          <span><strong>${r.name}</strong> <span style="color:#B9C5D0">(${r.size_kb} KB)</span></span>
          <a class="btn" href="${r.url}" download style="text-decoration:none;padding:4px 10px;">Download</a>
        </div>`
      ).join('');
    } else {
      relBox.textContent = 'Release packages ready in /releases.';
    }

    document.getElementById('home-logs').textContent = (ov.recent_logs || [])
      .map(l => `[${l.timestamp.slice(0, 19)}] [${l.level}] ${l.message}`)
      .join('\n');
  } catch (err) {
    console.error(err);
  }
}

async function refreshScreen(screenId) {
  await refreshOverview();
  if (screenId === 'tasks') return loadTasks();
  if (screenId === 'agents') return loadAgents();
  if (screenId === 'browser') return loadBrowser();
  if (screenId === 'models') return loadModels();
  if (screenId === 'memory') return loadMemory();
  if (screenId === 'developer') return loadProjects();
  if (screenId === 'monitor') return loadMonitor();
  if (screenId === 'security') return loadSecurity();
  if (screenId === 'plugins') return loadPlugins();
  if (screenId === 'voice') return loadVoice();
  if (screenId === 'settings') return loadSettings();
}

async function toggleEmergencyStop() {
  await api('/api/security/emergency-stop', { method: 'POST' });
  await refreshOverview();
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = '';
  const data = await api('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ prompt, conversation_id: activeConversationId }),
  });
  activeConversationId = data.conversation_id;
  document.getElementById('chat-history').textContent = data.messages
    .map(m => `${m.role === 'user' ? 'YOU' : `ULTRON [${m.provider}]`}: ${m.content}`)
    .join('\n\n');
}

async function loadVoice() {
  const v = await api('/api/voice');
  document.getElementById('voice-output').textContent = JSON.stringify(v, null, 2);
}

async function runVoiceTurn() {
  const wake_word = document.getElementById('voice-wake').value.trim();
  const utterance = document.getElementById('voice-utterance').value.trim() || 'Hey Ultron, system status';
  const out = await api('/api/voice/turn', { method: 'POST', body: JSON.stringify({ utterance, wake_word }) });
  document.getElementById('voice-output').textContent = JSON.stringify(out, null, 2);
}

async function interruptVoice() {
  const out = await api('/api/voice/interrupt', { method: 'POST' });
  document.getElementById('voice-output').textContent = 'SPEECH INTERRUPTED IMMEDIATELY:\n' + JSON.stringify(out, null, 2);
}

async function loadTasks() {
  const tasks = await api('/api/tasks');
  document.getElementById('tasks-tbody').innerHTML = tasks.map(t => `
    <tr>
      <td><code>${t.id}</code></td>
      <td><strong>${t.state}</strong></td>
      <td>${t.verified ? 'VERIFIED' : 'NO'}</td>
      <td>${t.category}</td>
      <td><strong>${t.objective}</strong><br/><span style="color:#B9C5D0">${t.result_summary || t.error_message || ''}</span></td>
      <td><button class="btn" onclick="cancelTask('${t.id}')">Cancel</button></td>
    </tr>
  `).join('');
}

async function submitTask() {
  const input = document.getElementById('task-objective');
  const alertBox = document.getElementById('task-alert');
  const objective = input.value.trim();
  if (!objective) return;
  alertBox.textContent = 'Planning, coordinating agents, executing & verifying...';
  try {
    await api('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ objective, priority: Number(document.getElementById('task-priority').value || 7) }),
    });
    alertBox.textContent = 'Task verified & completed!';
    input.value = '';
  } catch (err) {
    alertBox.textContent = err.message;
  }
  await loadTasks();
  await refreshOverview();
}

async function quickBuildInventory() {
  switchScreen('tasks');
  document.getElementById('task-objective').value =
    'ULTRON, build me a complete inventory management application with authentication, billing, stock management, reporting and an admin dashboard.';
  await submitTask();
}

async function cancelTask(id) {
  await api(`/api/tasks/${id}/cancel`, { method: 'POST' });
  await loadTasks();
}

async function loadAgents() {
  const agents = await api('/api/agents');
  document.getElementById('agents-tbody').innerHTML = agents.map(a => `
    <tr>
      <td><code>${a.agent_id}</code></td>
      <td>${a.display_name}</td>
      <td>${a.status.toUpperCase()}</td>
      <td>${a.heavy_inference ? 'Bounded' : 'Lightweight'}</td>
      <td>${a.specialty}</td>
    </tr>
  `).join('');
}

async function registerAgent() {
  const agent_id = document.getElementById('agent-id').value.trim();
  const display_name = document.getElementById('agent-name').value.trim();
  const specialty = document.getElementById('agent-spec').value.trim() || 'Custom specialist';
  if (!agent_id || !display_name) return;
  await api('/api/agents', { method: 'POST', body: JSON.stringify({ agent_id, display_name, specialty }) });
  await loadAgents();
}

async function loadBrowser() {
  const b = await api('/api/browser');
  document.getElementById('chrome-iso-card').innerHTML = `
    <div class="card-label">Environment A: Isolated Google Chrome Profile</div>
    <div>Personal Chrome Untouched: <strong style="color:#00E599">${b.chrome_isolation.user_chrome_untouched}</strong> |
    Cookies/Passwords Copied: <strong>${b.chrome_isolation.cookies_or_passwords_copied}</strong><br/>
    ULTRON Isolated Profile Dir: <code>${b.chrome_isolation.ultron_isolated_profile_dir}</code></div>
  `;
  document.getElementById('browser-output').textContent = JSON.stringify({ tabs: b.tabs, history: b.history.slice(0, 8) }, null, 2);
}

async function navigateBrowser() {
  const url_or_query = document.getElementById('browser-url').value.trim();
  const profile = document.getElementById('browser-profile').value;
  try {
    const tab = await api('/api/browser/navigate', { method: 'POST', body: JSON.stringify({ url_or_query, profile }) });
    document.getElementById('browser-output').textContent = JSON.stringify(tab, null, 2);
  } catch (err) {
    document.getElementById('browser-output').textContent = 'BLOCKED BY SECURITY / PAYMENT SHIELD:\n' + err.message;
  }
  await refreshOverview();
}

async function testBlockedPaymentUrl() {
  document.getElementById('browser-url').value = 'https://checkout.stripe.com/pay/cs_test_demo';
  await navigateBrowser();
}

async function loadModels() {
  const m = await api('/api/models');
  document.getElementById('models-tbody').innerHTML = m.providers.map(p => `
    <tr>
      <td><code>${p.id}</code></td>
      <td>${p.name}</td>
      <td>${p.mode}</td>
      <td>${p.configured ? 'READY' : 'Optional Key'}</td>
      <td>${p.ram_requirement}</td>
    </tr>
  `).join('');
}

async function saveVaultKey() {
  const key_name = document.getElementById('vault-key-name').value;
  const secret_value = document.getElementById('vault-secret-val').value.trim();
  if (!secret_value) return;
  await api('/api/models/secret', { method: 'POST', body: JSON.stringify({ key_name, secret_value }) });
  document.getElementById('vault-secret-val').value = '';
  await loadModels();
}

async function loadMemory() {
  const q = document.getElementById('mem-search').value.trim();
  const data = await api(`/api/memory?q=${encodeURIComponent(q)}`);
  document.getElementById('memory-tbody').innerHTML = data.memories.map(m => `
    <tr>
      <td><code>${m.id}</code></td>
      <td>${m.namespace}</td>
      <td><strong>${m.title}</strong></td>
      <td>${m.content}</td>
      <td><button class="btn" onclick="deleteMemory('${m.id}')">Delete</button></td>
    </tr>
  `).join('');
}

async function addMemory() {
  const namespace = document.getElementById('mem-ns').value;
  const title = document.getElementById('mem-title').value.trim();
  const content = document.getElementById('mem-content').value.trim();
  if (!title || !content) return;
  try {
    await api('/api/memory', { method: 'POST', body: JSON.stringify({ title, content, namespace }) });
    document.getElementById('mem-title').value = '';
    document.getElementById('mem-content').value = '';
    await loadMemory();
  } catch (err) {
    alert(err.message);
  }
}

async function deleteMemory(id) {
  await api(`/api/memory/${id}`, { method: 'DELETE' });
  await loadMemory();
}

async function searchFiles() {
  const pattern = document.getElementById('file-glob').value.trim() || '*';
  const q = document.getElementById('file-query').value.trim();
  const res = await api(`/api/files/search?pattern=${encodeURIComponent(pattern)}&q=${encodeURIComponent(q)}`);
  document.getElementById('files-output').textContent = JSON.stringify(res, null, 2);
}

async function evalCalc() {
  const expression = document.getElementById('calc-expr').value.trim();
  try {
    const res = await api('/api/files/calculate', { method: 'POST', body: JSON.stringify({ expression }) });
    document.getElementById('files-output').textContent = `Verified Calculation:\n${res.expression} = ${res.result}`;
  } catch (err) {
    document.getElementById('files-output').textContent = err.message;
  }
}

async function loadProjects() {
  const projs = await api('/api/developer/projects');
  document.getElementById('dev-tbody').innerHTML = projs.map(p => `
    <tr>
      <td><strong>${p.name}</strong></td>
      <td>${p.language}</td>
      <td>${p.verified ? 'VERIFIED' : 'FAILED'}</td>
      <td>${p.framework}</td>
      <td><code>${p.workspace_path}</code></td>
    </tr>
  `).join('');
}

async function buildSoftware() {
  const objective = document.getElementById('dev-spec').value.trim();
  const language = document.getElementById('dev-lang').value;
  document.getElementById('dev-output').textContent = 'Scaffolding isolated workspace, generating code, running automated tests & packaging...';
  try {
    const res = await api('/api/developer/build', { method: 'POST', body: JSON.stringify({ objective, language }) });
    document.getElementById('dev-output').textContent = JSON.stringify(res, null, 2);
  } catch (err) {
    document.getElementById('dev-output').textContent = err.message;
  }
  await loadProjects();
}

async function loadMonitor() {
  const m = await api('/api/system');
  document.getElementById('monitor-snapshot').textContent = JSON.stringify(m.snapshot, null, 2);
  document.getElementById('monitor-tbody').innerHTML = m.processes.map(p => `
    <tr><td>${p.pid}</td><td>${p.name}</td><td>${p.cpu_percent}%</td><td>${p.memory_mb}</td><td>${p.status}</td></tr>
  `).join('');
}

async function loadSecurity() {
  const s = await api('/api/security');
  document.getElementById('security-summary').textContent =
    `Audit Hash-Chain Integrity: ${s.audit_chain_valid ? 'VERIFIED' : 'BROKEN'} (${s.audit_entry_count} entries) | ` +
    `Payment Lockdown: ${s.payment_isolation_locked ? 'ACTIVE (' + s.payment_lockdown_reason + ')' : 'CLEAR'}`;
  document.getElementById('audit-tbody').innerHTML = s.audit_events.map(ev => `
    <tr>
      <td>${ev.created_at.slice(0, 19)}</td>
      <td>${ev.event_type}</td>
      <td>${ev.category}</td>
      <td><strong>${ev.decision}</strong></td>
      <td>${ev.details_redacted}</td>
    </tr>
  `).join('');
}

async function applyProfile(profile_name) {
  await api('/api/security/permissions', { method: 'POST', body: JSON.stringify({ profile_name }) });
  await loadSecurity();
}

async function revokeAllPermissions() {
  await api('/api/security/revoke-all', { method: 'POST' });
  await loadSecurity();
}

async function releasePaymentLock() {
  await api('/api/security/release-payment-lock', { method: 'POST' });
  await loadSecurity();
  await refreshOverview();
}

async function loadPlugins() {
  const skills = await api('/api/plugins');
  document.getElementById('plugins-tbody').innerHTML = skills.map(s => `
    <tr>
      <td><code>${s.skill_id}</code></td>
      <td><strong>${s.name}</strong></td>
      <td>${s.version}</td>
      <td>${s.enabled ? 'ENABLED' : 'DISABLED'}</td>
      <td>${s.description}</td>
      <td>
        <button class="btn primary" onclick="execSkill('${s.skill_id}')">Run Skill</button>
        <button class="btn" onclick="toggleSkill('${s.skill_id}')">Toggle</button>
      </td>
    </tr>
  `).join('');
}

async function execSkill(skill_id) {
  const out = await api('/api/plugins/execute', { method: 'POST', body: JSON.stringify({ skill_id, params: {} }) });
  document.getElementById('plugin-output').textContent = JSON.stringify(out, null, 2);
}

async function toggleSkill(skill_id) {
  await api(`/api/plugins/${skill_id}/toggle`, { method: 'POST' });
  await loadPlugins();
}

async function loadSettings() {
  const kit = await api('/api/brand-kit');
  document.getElementById('brand-gallery').innerHTML = kit.map(item => `
    <div class="brand-item">
      <div class="card-label">${item.title}</div>
      <img src="${item.url}" alt="${item.title}" />
      <div style="margin-top:8px;"><a class="btn" href="${item.url}" download="${item.file}" style="text-decoration:none;display:inline-block;">Download ${item.file}</a></div>
    </div>
  `).join('');
}

async function setModePolicy(policy) {
  const st = await api('/api/settings/mode', { method: 'POST', body: JSON.stringify({ policy }) });
  document.getElementById('settings-output').textContent = JSON.stringify(st, null, 2);
  await refreshOverview();
}

refreshOverview();
setInterval(refreshOverview, 5000);
