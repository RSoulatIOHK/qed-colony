/* QED Colony Observatory. No dependencies, mutations, or simulated activity. */
'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const arrays = ['agents', 'tasks', 'events', 'benchmarks', 'reviews'];
  const state = { data: null, view: 'overview', source: 'offline', loading: false, selection: null, benchmarkRun: null, benchmarkRunExplicit: false, benchmarkStrategy: 'colony' };
  const doneStatuses = new Set(['done', 'completed', 'merged', 'cancelled', 'canceled']);
  const runningStatuses = new Set(['working', 'running', 'active', 'in_progress', 'claimed', 'review']);
  const initial = { project: {}, agents: [], tasks: [], events: [], benchmarks: [], reviews: [] };
  const pretty = (value) => String(value ?? 'unspecified').replace(/[_-]/g, ' ');
  const printable = (value) => typeof value === 'object' && value !== null ? JSON.stringify(value, null, 2) : String(value ?? '');
  const status = (value) => String(value ?? 'unspecified').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
  const string = (value, fallback = '') => value === null || value === undefined ? fallback : String(value);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = string(text);
    return node;
  }

  function safeURL(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }

  function link(label, href, className = 'artifact-link') {
    const safe = safeURL(href);
    if (!safe) return null;
    const node = el('a', className, label);
    node.href = safe;
    node.target = '_blank';
    node.rel = 'noopener noreferrer';
    return node;
  }

  function badge(value) { return el('span', `status-badge status-${status(value)}`, pretty(value)); }
  function roleLabel(value) { return ({ sre: 'SRE', operations: 'Operations steward', triage: 'Blocker triage', 'blocker-triage': 'Blocker triage', 'repair-author': 'Repair author', controller: 'Controller' })[status(value)] || pretty(value); }
  function taskButton(task) {
    const button = el('button', 'task-title-button', task.title || task.id || 'Untitled task');
    button.type = 'button';
    button.dataset.task = string(task.id);
    return button;
  }

  function validDate(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date : null;
  }

  function dateTime(value) {
    const date = validDate(value);
    return date ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date) : 'Time not recorded';
  }

  function relative(value) {
    const date = validDate(value);
    if (!date) return 'Undated';
    const delta = Math.round((date.getTime() - Date.now()) / 1000);
    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto', style: 'short' });
    if (Math.abs(delta) < 60) return rtf.format(delta, 'second');
    if (Math.abs(delta) < 3600) return rtf.format(Math.round(delta / 60), 'minute');
    if (Math.abs(delta) < 86400) return rtf.format(Math.round(delta / 3600), 'hour');
    return rtf.format(Math.round(delta / 86400), 'day');
  }

  function empty(title, description, icon = '⌁') {
    const node = el('div', 'empty-state');
    const symbol = el('div', 'empty-icon', icon);
    symbol.setAttribute('aria-hidden', 'true');
    node.append(symbol, el('h3', '', title), el('p', '', description));
    return node;
  }

  function normalized(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('The state response is not an object.');
    const clean = { ...data, project: data.project && typeof data.project === 'object' ? data.project : {} };
    for (const key of arrays) clean[key] = Array.isArray(data[key]) ? data[key].filter((item) => item && typeof item === 'object') : [];
    return clean;
  }

  async function fetchJSON(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(path, { signal: controller.signal, cache: 'no-store', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return normalized(await response.json());
    } finally { clearTimeout(timeout); }
  }

  async function refresh() {
    if (state.loading) return;
    state.loading = true;
    $('refresh').disabled = true;
    $('refresh').setAttribute('aria-busy', 'true');
    let data = null;
    let source = 'offline';
    try {
      data = await fetchJSON('/api/state');
      source = data.mode === 'snapshot' ? 'snapshot-api' : 'live';
    } catch {
      try { data = await fetchJSON('./state.json'); source = 'snapshot'; } catch { /* Retain the last successful state. */ }
    }
    if (data) {
      state.data = data;
      state.source = source;
      $('load-error').hidden = true;
      render();
    } else {
      state.source = 'offline';
      if (!state.data) state.data = initial;
      render();
      $('load-error').textContent = 'No live endpoint or saved snapshot could be read. The view contains no new operational data. Check the connection, then refresh.';
      $('load-error').hidden = false;
    }
    renderSource();
    state.loading = false;
    $('refresh').disabled = false;
    $('refresh').removeAttribute('aria-busy');
  }

  function renderSource() {
    const data = state.data || initial;
    const source = state.source;
    $('connection-dot').className = `connection-dot ${source.startsWith('snapshot') ? 'snapshot' : source}`;
    $('source-label').textContent = source === 'live' ? 'Live colony state' : source.startsWith('snapshot') ? 'Saved snapshot' : 'Connection unavailable';
    $('source-time').textContent = data.generated_at ? `As of ${dateTime(data.generated_at)}` : 'Initial state · no timestamp recorded';
    $('source-note').textContent = source === 'live' ? 'Read-only · updates every 15 seconds' : source === 'snapshot-api' ? 'Runtime is serving a recorded snapshot' : source === 'snapshot' ? 'Live endpoint unavailable · showing saved state' : 'Last available state retained, if any';
    $('footer-source').textContent = `${source === 'live' ? 'LIVE' : source.startsWith('snapshot') ? 'SNAPSHOT' : 'OFFLINE'} / ${data.generated_at ? dateTime(data.generated_at) : 'NO RECORDED TIMESTAMP'}`;
  }

  function render() {
    const data = state.data;
    const repo = safeURL(data.project.repo_url);
    $('repo-link').hidden = !repo;
    if (repo) $('repo-link').href = repo;
    if (data.project.mission) $('mission-text').textContent = printable(data.project.mission);
    $('queue-count').textContent = String(data.tasks.length);
    const active = data.agents.filter((agent) => runningStatuses.has(status(agent.status))).length;
    const open = data.tasks.filter((task) => !doneStatuses.has(status(task.status))).length;
    const controller = controllerState();
    $('phase-label').textContent = controller.fresh ? (active ? 'Agent working' : controller.phase) : (open ? 'Work queued · controller unconfirmed' : 'Controller unconfirmed');
    $('phase-indicator').className = `phase-indicator ${controller.tone}`;
    $('map-count').textContent = data.agents.length || data.tasks.length ? `${data.agents.length} agent${data.agents.length === 1 ? '' : 's'} / ${data.tasks.length} task${data.tasks.length === 1 ? '' : 's'}` : 'Awaiting first agents';
    renderMap();
    renderAutonomy();
    renderRecovery();
    renderRoster();
    renderTasks();
    renderKanban();
    renderEvents();
    renderBenchmarks();
    renderReviews();
    renderSource();
    if ($('detail-dialog').open && state.selection) renderDetails(state.selection.kind, state.selection.id, false);
  }

  function controllerState() {
    const autonomy = state.data?.autonomy || {};
    const service = autonomy.service || {};
    const recorded = status(service.status);
    const heartbeat = validDate(service.heartbeat);
    const age = heartbeat ? (Date.now() - heartbeat.getTime()) / 1000 : Infinity;
    const fresh = state.source === 'live' && !!heartbeat && age >= -30 && age <= 120 && service.stale !== true;
    if (state.source.startsWith('snapshot')) return { label: heartbeat ? `Recorded: ${pretty(recorded)}` : 'Controller not recorded', tone: 'snapshot', fresh: false, phase: 'Saved snapshot' };
    if (['stopped', 'disabled', 'not_started'].includes(recorded)) return { label: 'Controller stopped', tone: 'stopped', fresh: false, phase: 'Stopped' };
    if (!heartbeat) return { label: 'Controller not reported', tone: 'unknown', fresh: false, phase: 'Unconfirmed' };
    if (!fresh) return { label: 'Controller heartbeat stale', tone: 'stale', fresh: false, phase: 'Heartbeat stale' };
    if (['budget_limited', 'waiting_budget', 'budget_exhausted'].includes(recorded)) return { label: 'Daily runtime limit reached', tone: 'waiting', fresh: true, phase: 'Waiting for daily reset' };
    if (['error', 'failed', 'blocked', 'needs_review'].includes(recorded)) return { label: 'Controller needs attention', tone: 'stale', fresh: true, phase: 'Needs attention' };
    if (recorded === 'capacity_limited') return { label: 'Model lanes occupied', tone: 'waiting', fresh: true, phase: 'Waiting for a model lane' };
    if (recorded === 'draining') return { label: 'Finishing active workers', tone: 'waiting', fresh: true, phase: 'Stopping admission' };
    if (['waiting', 'idle', 'waiting_ci', 'waiting_for_checks'].includes(recorded)) return { label: 'Controller waiting', tone: 'waiting', fresh: true, phase: service.active_cycle ? 'Waiting on a cycle' : 'Waiting for work' };
    return { label: 'Controller active', tone: 'active', fresh: true, phase: 'Autonomous loop active' };
  }

  function duration(value) {
    const total = Math.max(0, Math.round(Number(value) || 0));
    if (total >= 3600) return `${Math.floor(total / 3600)}h ${Math.floor(total % 3600 / 60)}m`;
    if (total >= 60) return `${Math.floor(total / 60)}m ${total % 60}s`;
    return `${total}s`;
  }

  function renderAutonomy() {
    const autonomy = state.data.autonomy || {};
    const service = autonomy.service || {};
    const budget = autonomy.budget || service.budget || {};
    const controller = controllerState();
    $('controller-label').textContent = controller.label;
    $('controller-dot').className = `controller-dot ${controller.tone}`;
    $('controller-message').textContent = state.source.startsWith('snapshot')
      ? 'This saved state cannot confirm whether the controller is running now.'
      : service.message || (controller.fresh ? 'The controller is reporting its actual state.' : 'Queued tasks and a reachable dashboard do not establish that the autonomous loop is running.');
    $('controller-heartbeat').textContent = service.heartbeat ? `Heartbeat ${dateTime(service.heartbeat)}${service.active_cycle ? ` · cycle ${service.active_cycle}` : ''}` : 'No heartbeat recorded';
    const modelPolicy = autonomy.model_policy || {};
    const workers = workerActivity();
    const concurrency = Number(budget.concurrency_limit || modelPolicy.max_concurrency) || 1;
    const activeCycleIDs = new Set(Array.isArray(budget.active_cycle_ids) ? budget.active_cycle_ids : []);
    $('controller-parallelism').textContent = state.source === 'live' && controller.fresh
      ? `${workers.active.length} model workers running · ${budget.active_attempts ?? '—'} calls reserved/running · up to ${concurrency} in parallel${budget.uncertain_workers ? ` · ${budget.uncertain_workers} worker outcomes need reconciliation` : ''}`
      : 'Current model workers unconfirmed. Saved counts describe their recorded time.';
    $('controller-model-policy').hidden = !modelPolicy.default_model;
    $('controller-model-policy').textContent = modelPolicy.default_model ? `Starts with ${modelPolicy.default_model} · ${modelPolicy.default_reasoning_effort || 'configured'} reasoning. ${modelPolicy.escalation || 'Escalation follows the recorded model policy.'}` : '';
    const limit = Number(budget.max_daily_seconds);
    const charged = Number(budget.used_seconds) || 0;
    const reserved = Number(budget.reserved_seconds) || 0;
    const used = Math.max(0, charged - reserved);
    const hasBudget = Number.isFinite(limit) && limit > 0;
    $('budget-remaining').textContent = hasBudget ? duration(budget.remaining_seconds) : '—';
    $('budget-limit').textContent = hasBudget ? `remaining of ${duration(limit)}` : 'No runtime limit reported';
    $('budget-date').textContent = budget.local_date ? `${budget.local_date} · ${budget.timezone || 'local day'}` : 'No date recorded';
    const percent = hasBudget ? Math.min(100, Math.max(0, charged / limit * 100)) : 0;
    $('budget-fill').style.width = `${percent}%`;
    $('budget-meter').setAttribute('aria-valuenow', String(Math.round(percent)));
    $('budget-meter').setAttribute('aria-valuetext', hasBudget ? `${duration(used)} used, ${duration(reserved)} reserved, ${duration(budget.remaining_seconds)} remaining` : 'No budget reported');
    $('budget-detail').textContent = hasBudget
      ? `${duration(used)} used${reserved ? ` · ${duration(reserved)} reserved` : ''} · ${budget.attempts ?? 0}/${budget.max_daily_attempts ?? '—'} attempts${budget.resets_at ? ` · resets ${dateTime(budget.resets_at)}` : ''}. Shared by all agent roles.`
      : 'Aggregate worker time, including implementation, planning, and review.';
    const cycles = Array.isArray(autonomy.cycles) ? autonomy.cycles : [];
    $('cycle-count').textContent = `${cycles.length} recorded · ${activeCycleIDs.size} with reserved/running calls`;
    const container = $('autonomy-cycles');
    container.replaceChildren();
    if (!cycles.length) {
      container.append(el('p', 'cycle-empty', 'No autonomous cycle has been recorded. Public PRs and their review and CI evidence will appear here.'));
      return;
    }
    const terminal = new Set(['complete', 'completed', 'done', 'merged', 'failed', 'blocked', 'abandoned', 'needs_review']);
    const ordered = [...cycles].sort((a, b) => Number(activeCycleIDs.has(b.id)) - Number(activeCycleIDs.has(a.id)) || Number(terminal.has(status(a.phase))) - Number(terminal.has(status(b.phase))) || string(b.updated_at || b.created_at).localeCompare(string(a.updated_at || a.created_at)));
    ordered.slice(0, 4).forEach((cycle) => {
      const card = el('article', 'cycle-card');
      const top = el('div', 'cycle-top');
      const task = state.data.tasks.find((item) => string(item.id) === string(cycle.task_id));
      if (task) top.append(taskButton(task)); else top.append(el('strong', '', cycle.task_id || cycle.id || 'Recorded cycle'));
      const integrationHold = cycle.governance_required === true && cycle.governance_status === 'awaiting_controller_integration' && cycle.ci_status === 'passed';
      top.append(integrationHold ? el('span', 'status-badge status-integration', 'Awaiting controller integration') : badge(cycle.phase));
      card.append(top, el('span', 'task-meta', `${cycle.id || 'Cycle'} · updated ${dateTime(cycle.updated_at || cycle.created_at)}`));
      if (activeCycleIDs.has(cycle.id)) card.append(el('p', 'cycle-running-note', 'Model call reserved/running'));
      if (integrationHold) card.append(el('p', 'cycle-integration-note', 'The reviewed governance PR passed CI and is ready for a controller integration decision.'));
      if (cycle.summary || cycle.message) card.append(el('p', '', printable(cycle.summary || cycle.message)));
      const evidence = el('div', 'cycle-evidence');
      const pr = link('Pull request ↗', cycle.pr_url);
      if (pr) evidence.append(pr);
      const review = cycle.review && typeof cycle.review === 'object' ? cycle.review : {};
      const verdict = cycle.review_verdict || review.verdict;
      evidence.append(el('span', '', verdict ? `Review: ${pretty(verdict)}` : 'Review: not recorded'));
      const reviewed = cycle.reviewed_sha || cycle.reviewed_head || review.head_sha;
      if (reviewed) evidence.append(el('span', 'cycle-sha', `Reviewed ${string(reviewed).slice(0, 10)}`));
      const head = cycle.head_sha || cycle.head_oid || cycle.head;
      if (head) evidence.append(el('span', 'cycle-sha', `Head ${string(head).slice(0, 10)}`));
      if (cycle.model) evidence.append(el('span', 'cycle-sha', `${cycle.model}${cycle.reasoning_effort ? ` · ${cycle.reasoning_effort}` : ''}`));
      card.append(evidence);
      if (cycle.model_reason) card.append(el('p', 'cycle-model-reason', printable(cycle.model_reason)));
      const checks = Array.isArray(cycle.checks) ? cycle.checks : Array.isArray(cycle.ci_checks) ? cycle.ci_checks : [];
      if (checks.length) {
        const checkList = el('div', 'cycle-checks');
        checks.forEach((check) => {
          const label = `${check.name || check.context || 'CI'}: ${pretty(check.conclusion || check.state || check.status)}`;
          checkList.append(link(label, check.detailsUrl || check.details_url || check.url, 'check-link') || el('span', '', label));
        });
        card.append(checkList);
      } else card.append(el('p', 'cycle-ci-note', cycle.ci_status ? `CI: ${pretty(cycle.ci_status)}` : 'CI results not recorded.'));
      if (cycle.last_error) card.append(el('p', 'cycle-error', printable(cycle.last_error)));
      container.append(card);
    });
  }

  function laneFor(item) {
    const text = `${item.role || ''} ${item.title || ''}`.toLowerCase();
    if (/review|skeptic|scrutiny/.test(text)) return 2;
    if (/verif|kernel|proof specialist|validat|acceptance|certif/.test(text)) return 3;
    if (/research|benchmark|scout|experiment|architect|lead/.test(text)) return 0;
    return 1;
  }

  function renderMap() {
    const { agents, tasks } = state.data;
    const all = [
      ...tasks.slice(0, 20).map((item) => ({ item, kind: 'task', lane: laneFor(item) })),
      ...agents.slice(0, 12).map((item) => ({ item, kind: 'agent', lane: laneFor(item) }))
    ];
    $('map-empty').hidden = all.length > 0;
    const nodes = $('graph-nodes');
    const lines = $('connections');
    nodes.replaceChildren();
    lines.replaceChildren();
    const positions = new Map();
    for (let lane = 0; lane < 4; lane += 1) {
      const laneItems = all.filter((entry) => entry.lane === lane);
      laneItems.forEach((entry, index) => {
        const x = 12.5 + lane * 25;
        const y = 22 + (index + .5) * 65 / Math.max(laneItems.length, 1);
        positions.set(`${entry.kind}:${entry.item.id}`, { x, y });
        const button = el('button', `graph-node ${entry.kind}-node`);
        button.type = 'button';
        button.dataset[entry.kind] = string(entry.item.id);
        const label = entry.kind === 'agent' ? entry.item.name || entry.item.id : entry.item.title || entry.item.id;
        button.title = `${entry.kind === 'agent' ? 'Agent' : 'Task'}: ${string(label)} · ${pretty(entry.item.status)}`;
        button.setAttribute('aria-label', button.title);
        button.style.left = `${x}%`;
        button.style.top = `${y}%`;
        const statusNode = el('span', 'node-status');
        statusNode.append(el('i', status(entry.item.status)), document.createTextNode(pretty(entry.item.status)));
        button.append(el('span', 'node-label', label), statusNode);
        nodes.append(button);
      });
    }
    function connect(from, to, agent = false) {
      if (!from || !to) return;
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const x1 = from.x * 10, x2 = to.x * 10, y1 = from.y * 4.4, y2 = to.y * 4.4;
      const bend = x1 === x2 ? 50 : Math.abs(x2 - x1) * .45;
      path.setAttribute('d', `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`);
      if (agent) path.setAttribute('class', 'agent-connection');
      lines.append(path);
    }
    tasks.slice(0, 20).forEach((task) => {
      const deps = Array.isArray(task.depends_on) ? task.depends_on : [];
      deps.forEach((id) => connect(positions.get(`task:${id}`), positions.get(`task:${task.id}`)));
    });
    agents.slice(0, 12).forEach((agent) => {
      if (agent.task_id) connect(positions.get(`agent:${agent.id}`), positions.get(`task:${agent.task_id}`), true);
    });
    const remaining = Math.max(0, tasks.length - 20) + Math.max(0, agents.length - 12);
    if (remaining) nodes.append(el('span', 'graph-overflow', `+${remaining} more · inspect the full research queue`));
  }

  function sortedTasks(tasks) {
    const priority = (task) => typeof task.priority === 'number' ? task.priority : ({ urgent: 100, high: 90, medium: 50, normal: 50, low: 10 }[status(task.priority)] ?? 0);
    const rank = (task) => {
      const value = status(task.status);
      if (['working', 'running', 'active', 'in_progress', 'claimed'].includes(value)) return 0;
      if (['review', 'in_review', 'awaiting_review'].includes(value)) return 1;
      if (['ready', 'queued', 'pending', 'open'].includes(value)) return 2;
      if (value === 'blocked') return 3;
      if (doneStatuses.has(value)) return 5;
      return 4;
    };
    return [...tasks].sort((a, b) => rank(a) - rank(b) || priority(b) - priority(a) || String(b.updated_at || '').localeCompare(String(a.updated_at || '')) || string(a.id).localeCompare(string(b.id)));
  }

  function renderRoster() {
    const agents = state.data.agents;
    const workers = workerActivity();
    const controller = controllerState();
    $('agent-roster-panel').hidden = !agents.length;
    $('roster-count').textContent = state.source.startsWith('snapshot')
      ? `${workers.recorded.length} running in snapshot · ${agents.length} recorded`
      : state.source !== 'live' ? `Current count unconfirmed · ${agents.length} recorded`
        : `${workers.active.length ? `${workers.active.length} running` : '0 model workers'} · ${agents.length} recorded`;
    $('roster-phase').textContent = rosterPhase(controller, workers.active.length);
    $('roster-explanation').textContent = `Workers start on demand; idle entries are past worker sessions. Publishing and CI can run with no model worker.${workers.unconfirmed.length && state.source === 'live' ? ` ${workers.unconfirmed.length} older working record${workers.unconfirmed.length === 1 ? ' has' : 's have'} no recent worker heartbeat.` : ''}`;
    const roster = $('agent-roster');
    roster.replaceChildren();
    const activeIDs = new Set(workers.active.map((agent) => agent.id));
    [...agents].sort((a, b) => Number(activeIDs.has(b.id)) - Number(activeIDs.has(a.id)) || string(b.last_seen).localeCompare(string(a.last_seen))).forEach((agent) => {
      const card = el('div', 'roster-agent');
      const heading = el('div', 'roster-agent-heading');
      const button = el('button', 'task-title-button', agent.name || agent.id || 'Unnamed agent');
      button.type = 'button';
      button.dataset.agent = string(agent.id);
      heading.append(button, badge(agent.status));
      card.append(heading, el('span', 'task-meta', roleLabel(agent.role || 'Role unspecified')));
      const task = state.data.tasks.find((entry) => entry.id === agent.task_id);
      if (task) { const assignment = taskButton(task); assignment.classList.add('roster-assignment'); card.append(assignment); }
      else card.append(el('span', 'task-meta', agent.task_id ? `Task: ${string(agent.task_id)}` : 'No recorded assignment'));
      card.append(el('span', 'task-meta roster-session-time', `${activeIDs.has(agent.id) ? 'Worker heartbeat' : 'Last recorded'} ${agent.last_seen ? dateTime(agent.last_seen) : 'time unavailable'}`));
      roster.append(card);
    });
  }

  function workerActivity() {
    const recorded = state.data.agents.filter((agent) => runningStatuses.has(status(agent.status)));
    const active = state.source === 'live' ? recorded.filter((agent) => {
      const at = validDate(agent.last_seen);
      const age = at ? (Date.now() - at.getTime()) / 1000 : Infinity;
      return age >= -30 && age <= 120;
    }) : [];
    const activeIDs = new Set(active.map((agent) => agent.id));
    return { recorded, active, unconfirmed: recorded.filter((agent) => !activeIDs.has(agent.id)) };
  }

  function rosterPhase(controller, activeWorkers) {
    if (state.source.startsWith('snapshot')) return 'Saved snapshot · current workers unconfirmed';
    if (state.source !== 'live') return 'Offline · current workers and controller unconfirmed';
    if (!controller.fresh) return controller.label;
    if (activeWorkers > 1) return `${activeWorkers} model workers running in parallel`;
    const autonomy = state.data.autonomy || {};
    const service = autonomy.service || {};
    if (['budget_limited', 'waiting_budget', 'budget_exhausted'].includes(status(service.status))) return 'Controller waiting for the daily runtime reset';
    const cycle = (Array.isArray(autonomy.cycles) ? autonomy.cycles : []).find((item) => item.id === service.active_cycle);
    if (!cycle) return controller.phase;
    const task = state.data.tasks.find((item) => item.id === cycle.task_id);
    const phases = {
      queued: 'Controller selecting work',
      authoring: activeWorkers ? 'Implementation underway' : 'Controller handing off to implementation',
      publishing: 'Controller publishing a PR',
      reviewing: activeWorkers ? 'Independent review underway' : 'Controller handing off to review',
      review_publication: 'Controller publishing the review',
      ci: 'Controller waiting for CI',
      merging: 'Controller merging reviewed work',
      done: 'Controller completed a cycle',
      needs_review: 'Controller needs attention',
      failed: 'Controller recorded a failed cycle'
    };
    return `${phases[status(cycle.phase)] || `Controller phase: ${pretty(cycle.phase)}`}${task ? ` · ${task.id}: ${task.title}` : cycle.task_id ? ` · ${cycle.task_id}` : ''}`;
  }

  function ownerFor(task) {
    if (!task.lease_owner) return 'Unassigned';
    return state.data.agents.find((agent) => agent.id === task.lease_owner)?.name || task.lease_owner;
  }

  function updateOptions(select, values, defaultText) {
    const previous = select.value;
    const nextValues = [...new Set(values.filter(Boolean).map(String))].sort();
    const existing = [...select.options].slice(1).map((option) => option.value);
    if (JSON.stringify(nextValues) === JSON.stringify(existing)) return;
    select.replaceChildren(new Option(defaultText, 'all'));
    nextValues.forEach((value) => select.add(new Option(pretty(value), value)));
    select.value = nextValues.includes(previous) ? previous : 'all';
  }

  function renderTasks() {
    const tasks = sortedTasks(state.data.tasks);
    const overview = $('overview-tasks');
    overview.replaceChildren();
    if (!tasks.length) overview.append(empty('A clean slate for the first hypothesis.', 'Accepted tasks will appear here with their actual status and evidence. No work has been reported yet.'));
    tasks.slice(0, 3).forEach((task) => {
      const row = el('div', 'mini-task');
      const title = el('div');
      title.append(taskButton(task), el('span', 'task-meta', `${task.id || 'Task'} / ${roleLabel(task.role || 'Role unassigned')}`));
      row.append(title, badge(task.status));
      overview.append(row);
    });
    updateOptions($('task-status'), tasks.map((task) => task.status), 'All statuses');
    renderQueue();
  }

  function renderQueue() {
    const query = $('task-search').value.toLowerCase().trim();
    const selectedStatus = $('task-status').value;
    const tasks = sortedTasks(state.data.tasks).filter((task) => (selectedStatus === 'all' || task.status === selectedStatus) && `${task.title || ''} ${task.id || ''} ${task.role || ''} ${task.description || ''}`.toLowerCase().includes(query));
    const list = $('queue-list');
    list.replaceChildren();
    if (!tasks.length) {
      list.append(empty(state.data.tasks.length ? 'No tasks match this view.' : 'The queue is ready for its first task.', state.data.tasks.length ? 'Try a different status or search term.' : 'Research proposals become durable assignments with explicit acceptance criteria.'));
      return;
    }
    tasks.forEach((task) => {
      const row = el('div', 'queue-row');
      const title = el('div');
      title.append(taskButton(task), el('span', 'task-meta', `${task.id || 'Task'}${task.priority !== undefined && task.priority !== null ? ` / priority ${pretty(task.priority)}` : ''}`));
      const owner = el('div', 'owner-label', roleLabel(task.role || 'Unspecified role'));
      owner.append(el('span', 'task-meta', ownerFor(task)));
      row.append(title, owner, badge(task.status), link('View PR ↗', task.pr_url) || el('span', 'no-artifact', '—'));
      list.append(row);
    });
  }

  function githubProjectURL(value) {
    const safe = safeURL(value);
    if (!safe) return null;
    const url = new URL(safe);
    return url.hostname === 'github.com' && !url.port && /^\/(?:users|orgs)\/[^/]+\/projects\/\d+(?:\/views\/\d+)?\/?$/.test(url.pathname) ? safe : null;
  }

  function cycleForTask(task) {
    const cycles = state.data.autonomy?.cycles;
    if (!Array.isArray(cycles)) return null;
    return cycles.filter((cycle) => cycle && string(cycle.task_id) === string(task.id))
      .sort((a, b) => string(b.updated_at || b.created_at).localeCompare(string(a.updated_at || a.created_at)))[0] || null;
  }

  function recoveryRoot(cycle) {
    if (!cycle) return null;
    if (cycle.recovery_root_id) {
      const cycles = state.data.autonomy?.cycles;
      return Array.isArray(cycles) ? cycles.find((entry) => string(entry.id) === string(cycle.recovery_root_id)) || null : null;
    }
    return cycle.recovery_status || cycle.recovery_owner ? cycle : null;
  }

  function recoveryLabel(value) {
    return ({ triage_queued: 'Triage queued', triaging: 'Diagnosing blocker', repair_queued: 'Repair queued',
      repair_in_progress: 'Repair in progress', repair_merged: 'Repair merged · reconciliation pending',
      escalated: 'Escalated · controller action required', awaiting_controller_integration: 'Controller integration required',
      controller_scope_review: 'Controller scope review required', resolved: 'Resolved' })[value] || pretty(value || 'Recovery state not reported');
  }

  function recoveryText(parent, label, value, className = '') {
    if (!value) return;
    const paragraph = el('p', `recovery-field ${className}`.trim());
    paragraph.append(el('strong', '', `${label}: `), document.createTextNode(printable(value)));
    parent.append(paragraph);
  }

  function recoveryTaskLink(container, label, id) {
    if (!id) return;
    const task = state.data.tasks.find((entry) => string(entry.id) === string(id));
    const row = el('div', 'recovery-task-link');
    row.append(el('span', '', `${label}: `));
    if (task) {
      const button = taskButton(task);
      button.textContent = `${task.id} · ${task.title || 'Inspect task'}`;
      row.append(button);
    } else row.append(el('span', '', string(id)));
    container.append(row);
  }

  function recoveryDetails(task, cycle, compact = false) {
    const root = recoveryRoot(cycle);
    if (!root) return null;
    const value = root.recovery_status;
    const controllerRequired = ['escalated', 'awaiting_controller_integration', 'controller_scope_review'].includes(value);
    const node = el('div', `recovery-case${compact ? ' recovery-compact' : ''}${controllerRequired ? ' recovery-controller-required' : ''}`);
    const heading = el('div', 'recovery-case-heading');
    heading.append(el('strong', '', cycle?.recovery_kind ? `${pretty(cycle.recovery_kind)} for ${root.task_id || 'parked work'}` : 'Recovery'));
    heading.append(el('span', `status-badge ${value === 'resolved' ? 'status-done' : controllerRequired ? 'status-blocked' : 'status-review'}`, recoveryLabel(value)));
    node.append(heading);
    recoveryText(node, 'Owner', root.recovery_owner ? roleLabel(root.recovery_owner) : 'Not reported');
    recoveryText(node, 'Next action', root.recovery_next_action || 'Not reported', 'recovery-next-action');
    if (root.recovery_next_action_deadline && value !== 'resolved') recoveryText(node, 'Next action due', dateTime(root.recovery_next_action_deadline));
    if (!compact) {
      recoveryText(node, 'Reason', root.recovery_reason);
      recoveryText(node, 'Diagnosis', root.recovery_diagnosis);
      if (root.source_head_sha) recoveryText(node, 'Source head', string(root.source_head_sha).slice(0, 12));
      const sourcePR = link('Source pull request ↗', root.source_pr_url);
      if (sourcePR) node.append(sourcePR);
      const cycles = Array.isArray(state.data.autonomy?.cycles) ? state.data.autonomy.cycles : [];
      const triage = cycles.find((entry) => string(entry.id) === string(root.recovery_triage_cycle_id));
      if (triage && string(triage.task_id) !== string(task.id)) recoveryTaskLink(node, 'Triage', triage.task_id);
    }
    if (cycle?.recovery_root_id && string(root.task_id) !== string(task.id)) recoveryTaskLink(node, 'Original task', root.task_id);
    if (root.recovery_repair_task_id && string(root.recovery_repair_task_id) !== string(task.id)) recoveryTaskLink(node, 'Repair task', root.recovery_repair_task_id);
    if (controllerRequired) node.append(el('p', 'recovery-attention', 'Controller action required. This case does not grant permission to change scope or deploy.'));
    else if (value === 'repair_merged') node.append(el('p', 'recovery-attention', 'The original blocker remains open until acceptance and remote reconciliation are recorded.'));
    return node;
  }

  function renderRecovery() {
    const cycles = Array.isArray(state.data.autonomy?.cycles) ? state.data.autonomy.cycles : [];
    const cases = cycles.filter((cycle) => !cycle.recovery_root_id && (cycle.recovery_status || cycle.recovery_owner));
    $('recovery-panel').hidden = !cases.length;
    const unresolved = cases.filter((cycle) => cycle.recovery_status !== 'resolved').length;
    $('recovery-count').textContent = `${unresolved} open / ${cases.length} recorded case${cases.length === 1 ? '' : 's'}`;
    const list = $('recovery-cases');
    list.replaceChildren();
    cases.sort((a, b) => Number(a.recovery_status === 'resolved') - Number(b.recovery_status === 'resolved') || string(a.recovery_next_action_deadline).localeCompare(string(b.recovery_next_action_deadline)) || string(a.task_id).localeCompare(string(b.task_id)));
    cases.forEach((cycle) => {
      const card = el('article', 'recovery-overview-card');
      const task = state.data.tasks.find((entry) => string(entry.id) === string(cycle.task_id));
      const heading = el('h3');
      if (task) {
        const button = taskButton(task);
        button.textContent = `${task.id} · ${task.title || 'Inspect task'}`;
        heading.append(button);
      } else heading.append(el('span', '', cycle.task_id || cycle.id || 'Recorded recovery case'));
      card.append(heading);
      const details = recoveryDetails(task || { id: cycle.task_id }, cycle);
      if (details) card.append(details);
      list.append(card);
    });
  }

  function boardStage(task, cycle) {
    const value = status(task.status);
    const phase = status(cycle?.phase);
    const review = cycle?.review && typeof cycle.review === 'object' ? cycle.review : {};
    const verdict = status(cycle?.review_verdict || review.verdict);
    const autonomy = state.data.autonomy || {};
    const budget = autonomy.budget || autonomy.service?.budget || {};
    const workers = workerActivity();
    const active = (state.source.startsWith('snapshot') ? workers.recorded : workers.active).some((agent) => string(agent.task_id) === string(task.id));
    const integrationHold = cycle?.governance_required === true && cycle.governance_status === 'awaiting_controller_integration';
    if (doneStatuses.has(value) || ['done', 'completed', 'merged'].includes(phase)) return { lane: 'done', label: value === 'cancelled' || value === 'canceled' ? 'Cancelled' : 'Completed', tone: 'done' };
    if (value === 'failed' || phase === 'failed') return { lane: 'blocked', label: 'Failed · needs intervention', tone: 'failed' };
    if (integrationHold) return { lane: 'blocked', label: 'Awaiting controller integration', tone: 'integration' };
    if (['blocked', 'needs_review', 'abandoned'].includes(phase) || ['blocked', 'needs_review'].includes(value)) return { lane: 'blocked', label: phase === 'needs_review' ? 'Needs intervention' : 'Blocked', tone: 'blocked' };
    if (['changes_requested', 'request_changes', 'reject', 'rejected'].includes(verdict) && !(phase === 'authoring' && active)) return { lane: 'blocked', label: 'Review requested changes', tone: 'blocked' };
    if (budget.exhausted === true && !active && ['queued', 'authoring', 'reviewing'].includes(phase)) return { lane: 'blocked', label: 'Daily model budget exhausted', tone: 'blocked' };
    if (phase === 'authoring') return { lane: 'progress', label: active ? 'Worker active' : 'Implementation recorded', tone: 'working' };
    if (['reviewing', 'review_publication', 'review_requested', 'ci', 'merging', 'publishing'].includes(phase) || ['review', 'in_review', 'awaiting_review', 'review_requested'].includes(value)) return { lane: 'review', label: ({ ci: 'Waiting for CI', merging: 'Ready for merge gate', publishing: 'Publishing PR', reviewing: 'Independent review', review_publication: 'Publishing review' })[phase] || 'Awaiting review', tone: 'review' };
    if (['working', 'running', 'active', 'in_progress', 'claimed'].includes(value)) return { lane: 'progress', label: active ? 'Worker active' : 'Implementation recorded', tone: 'working' };
    if (value === 'ready' || phase === 'queued') return { lane: 'ready', label: budget.exhausted === true ? 'Ready · waiting for daily budget' : 'Ready to be claimed', tone: 'ready' };
    return { lane: 'backlog', label: pretty(task.status || 'backlog'), tone: 'pending' };
  }

  function boardCard(task, cycle, stage) {
    const card = el('article', `kanban-card kanban-card-${stage.lane}`);
    const meta = el('div', 'kanban-card-top');
    meta.append(el('span', 'kanban-task-id', task.id || 'Task'), el('span', 'kanban-role-label', roleLabel(task.role || cycle?.role || 'Role unassigned')));
    const heading = el('h4');
    heading.append(taskButton(task));
    card.append(meta, heading, el('span', `status-badge status-${stage.tone}`, stage.label));
    if (task.lease_owner) card.append(el('p', 'kanban-owner', `Owner: ${ownerFor(task)}`));
    const phase = cycle?.phase;
    if (phase) card.append(el('p', 'kanban-phase', `Cycle: ${pretty(phase)}${cycle.revision !== undefined ? ` · revision ${cycle.revision}` : ''}`));
    const review = cycle?.review && typeof cycle.review === 'object' ? cycle.review : {};
    const verdict = cycle?.review_verdict || review.verdict;
    if (cycle) card.append(el('p', 'kanban-evidence', [verdict ? `Review: ${pretty(verdict)}` : 'Review: not recorded', cycle.ci_status ? `CI: ${pretty(cycle.ci_status)}` : 'CI: not recorded'].join(' · ')));
    const reviewed = cycle?.reviewed_sha || cycle?.reviewed_head || review.head_sha;
    const head = cycle?.head_sha || cycle?.head_oid || cycle?.head;
    if (reviewed) card.append(el('p', 'kanban-evidence', `Reviewed head: ${string(reviewed).slice(0, 10)}`));
    if (reviewed && head && reviewed !== head) card.append(el('p', 'kanban-blocker', 'Recorded review applies to an earlier head.'));
    const dependencyIDs = Array.isArray(task.depends_on) ? task.depends_on : [];
    const unmet = dependencyIDs.filter((id) => !doneStatuses.has(status(state.data.tasks.find((entry) => string(entry.id) === string(id))?.status)));
    if (unmet.length) card.append(el('p', 'kanban-blocker', `Dependencies: ${unmet.join(', ')}`));
    const reason = cycle?.last_error || ((stage.lane === 'blocked' || stage.lane === 'done') && task.summary);
    if (reason) {
      const text = printable(reason);
      const note = el('p', 'kanban-blocker', text.length > 320 ? `${text.slice(0, 317)}…` : text);
      note.title = text;
      card.append(note);
    }
    const recovery = recoveryDetails(task, cycle, true);
    if (recovery) card.append(recovery);
    const links = el('div', 'kanban-card-links');
    const pr = link('Pull request ↗', cycle?.pr_url || task.pr_url);
    const issue = link('Issue ↗', task.issue_url);
    if (pr) links.append(pr);
    if (issue) links.append(issue);
    if (links.childElementCount) card.append(links);
    return card;
  }

  function renderKanban() {
    const project = state.data.project || {};
    const projectURL = githubProjectURL(project.github_project_url) || githubProjectURL(project.project_url);
    const projectLink = $('github-project-link');
    projectLink.hidden = !projectURL;
    if (projectURL) projectLink.href = projectURL; else projectLink.removeAttribute('href');
    const tasks = sortedTasks(state.data.tasks);
    updateOptions($('kanban-role'), tasks.map((task) => task.role), 'All roles');
    const query = $('kanban-search').value.trim().toLowerCase();
    const role = $('kanban-role').value;
    const entries = tasks.map((task) => {
      const cycle = cycleForTask(task);
      return { task, cycle, stage: boardStage(task, cycle) };
    }).filter(({ task, cycle, stage }) => (role === 'all' || string(task.role) === role) && [task.id, task.title, task.role, task.description, task.pr_url, task.issue_url, cycle?.pr_url, cycle?.phase, cycle?.last_error, cycle?.recovery_owner, cycle?.recovery_status, cycle?.recovery_next_action, cycle?.recovery_diagnosis, stage.label].filter(Boolean).join(' ').toLowerCase().includes(query));
    $('kanban-count').textContent = `${entries.length} of ${tasks.length} recorded task${tasks.length === 1 ? '' : 's'}${state.source.startsWith('snapshot') ? ' · saved snapshot' : state.source !== 'live' ? ' · current state unconfirmed' : ''}`;
    const autonomy = state.data.autonomy || {};
    const budget = autonomy.budget || autonomy.service?.budget || {};
    const notice = $('kanban-budget');
    notice.hidden = budget.exhausted !== true;
    notice.textContent = budget.exhausted === true ? `Daily model budget exhausted${budget.attempts !== undefined && budget.max_daily_attempts !== undefined ? ` (${budget.attempts}/${budget.max_daily_attempts} attempts)` : ''}. New model work waits${budget.resets_at ? ` until ${dateTime(budget.resets_at)}` : ' for the daily reset'}. Already reserved work and non-model controller steps may still finish.` : '';
    const board = $('kanban-board');
    board.replaceChildren();
    const lanes = [['backlog', 'Backlog'], ['ready', 'Ready'], ['progress', 'In progress'], ['review', 'Review'], ['blocked', 'Blocked'], ['done', 'Done']];
    lanes.forEach(([key, label]) => {
      const laneEntries = entries.filter((entry) => entry.stage.lane === key);
      const column = el('section', `kanban-column kanban-column-${key}`);
      column.setAttribute('aria-labelledby', `kanban-lane-${key}`);
      const heading = el('div', 'kanban-column-heading');
      const title = el('h3', '', label);
      title.id = `kanban-lane-${key}`;
      heading.append(title, el('span', 'kanban-column-count', laneEntries.length));
      const cards = el('div', 'kanban-cards');
      if (!laneEntries.length) cards.append(el('p', 'kanban-empty', query || role !== 'all' ? 'No matching tasks' : 'No recorded tasks'));
      laneEntries.forEach(({ task, cycle, stage }) => cards.append(boardCard(task, cycle, stage)));
      column.append(heading, cards);
      board.append(column);
    });
  }

  function orderedEvents() {
    return state.data.events.map((event, index) => ({ event, index })).sort((a, b) => string(b.event.at).localeCompare(string(a.event.at)) || (Number.isFinite(Number(a.event.id)) && Number.isFinite(Number(b.event.id)) ? Number(b.event.id) - Number(a.event.id) : b.index - a.index)).map(({ event }) => event);
  }

  function eventRow(event, full = false) {
    const row = el('div', 'event-row');
    const copy = el('div');
    copy.append(el('p', 'event-message', event.message || pretty(event.kind || 'Recorded event')));
    const actor = state.data.agents.find((agent) => agent.id === event.actor)?.name || event.actor || 'Runtime';
    copy.append(el('span', 'task-meta', `${string(actor)} / ${pretty(event.kind || 'event')}${event.task_id ? ` / ${string(event.task_id)}` : ''}`));
    if (full && event.task_id && state.data.tasks.some((task) => task.id === event.task_id)) {
      const button = el('button', 'text-button', 'Inspect task ↗');
      button.type = 'button';
      button.dataset.task = string(event.task_id);
      copy.append(button);
    }
    const time = el('time', 'event-time', full ? dateTime(event.at) : relative(event.at));
    const valid = validDate(event.at);
    if (valid) time.dateTime = valid.toISOString();
    time.title = dateTime(event.at);
    row.append(el('span', 'event-marker'), copy, time);
    return row;
  }

  function renderEvents() {
    const events = orderedEvents();
    const overview = $('overview-events');
    overview.replaceChildren();
    if (!events.length) overview.append(empty('The record begins with real work.', 'Task updates, experiment outcomes, and review decisions will be shown as the colony records them.', '↳'));
    events.slice(0, 3).forEach((event) => overview.append(eventRow(event)));
    updateOptions($('event-kind'), events.map((event) => event.kind), 'All event types');
    renderActivity();
  }

  function renderActivity() {
    const filter = $('event-kind').value;
    const events = orderedEvents().filter((event) => filter === 'all' || event.kind === filter);
    const list = $('activity-list');
    list.replaceChildren();
    if (!events.length) list.append(empty('No recorded events in this view.', 'The event log is a durable account of actual work. Refresh to read the latest available state.', '↳'));
    events.forEach((event) => list.append(eventRow(event, true)));
  }

  function trustFor(result) {
    if (result.assurance === 'none' || status(result.status) === 'proof_failed') return { label: 'No checked proof', className: '' };
    if (result.assurance === 'lean_kernel') {
      const certified = ['certified', 'kernel_checked', 'proved', 'passed', 'success'].includes(status(result.status));
      return certified ? { label: 'Kernel checked', className: 'trust-kernel' } : { label: 'No checked proof', className: '' };
    }
    const trust = status(result.trust_category || result.trust || result.verification || 'unspecified');
    if (['kernel_checked', 'kernel-checked', 'independently_checked', 'kernel'].includes(trust)) return { label: 'Kernel checked', className: 'trust-kernel' };
    if (['reconstructed', 'proof_reconstructed'].includes(trust)) return { label: 'Reconstructed', className: 'trust-reconstructed' };
    if (['solver', 'solver_result', 'solver_success'].includes(trust)) return { label: 'Solver result', className: 'trust-solver' };
    return { label: 'Unspecified', className: '' };
  }

  const liveStrategies = [['colony', 'Colony'], ['simp', 'simp_all'], ['omega', 'omega'], ['grind', 'grind']];

  function liveResultLabel(result, kind) {
    if (kind === 'negative' && result.status === 'kernel_accepted') return 'INVALID CONTROL ACCEPTED';
    if (kind === 'negative' && result.status === 'proof_failed') return 'Rejected as expected';
    return ({ kernel_accepted: 'Kernel accepted', proof_failed: 'No proof', timeout: 'Time limit',
      error: 'Harness error', disallowed_axioms: 'Disallowed axioms', missing_axiom_evidence: 'Missing kernel evidence' })[result.status] || 'Unrecognized outcome';
  }

  function liveCaseCard(item, control = false) {
    const card = el('details', 'live-benchmark-case');
    const heading = el('summary');
    heading.append(el('strong', '', item.source_name), el('span', 'subtle-label', control ? pretty(item.kind) : item.id));
    card.append(heading, el('pre', 'live-statement', item.header));
    const provenance = el('div', 'live-case-provenance');
    const upstream = link(item.source_line ? `Original source · line ${item.source_line} ↗` : 'Original source ↗', item.source_url);
    if (upstream) provenance.append(upstream);
    provenance.append(el('span', '', `Statement SHA-256: ${item.statement_sha256}`));
    card.append(provenance);
    const outcomes = el('div', 'live-case-outcomes');
    liveStrategies.forEach(([strategy, label]) => {
      const result = item.results[strategy];
      const row = el('div', 'live-case-outcome');
      const accepted = result.status === 'kernel_accepted';
      row.append(el('strong', '', label), el('code', '', result.proof_body),
        el('span', accepted && item.kind === 'negative' ? 'live-result-error' : accepted ? 'live-result-proved' : 'live-result-unproved', liveResultLabel(result, item.kind)),
        el('span', 'subtle-label', `${Number(result.wall_seconds).toFixed(3)} s`));
      const evidence = el('details', 'live-generated-source');
      evidence.append(el('summary', '', 'Generated declaration and axiom evidence'),
        el('p', '', `Generated source SHA-256: ${result.generated_source_sha256}`),
        el('p', '', `Axioms: ${Array.isArray(result.axioms) ? result.axioms.length ? result.axioms.join(', ') : 'none (reported axiom-free)' : 'no axiom evidence produced'}`),
        el('pre', '', result.generated_source));
      row.append(evidence);
      outcomes.append(row);
    });
    card.append(outcomes);
    return card;
  }

  function renderLiveBenchmark() {
    const container = $('live-benchmark');
    container.replaceChildren();
    const live = state.data.live_benchmark || {};
    const recorded = live.status || {};
    const report = live.report;
    const current = state.source === 'live';
    const stale = !current || recorded.stale !== false;
    const invalid = report?.valid === false;
    const heading = el('div', 'live-benchmark-heading');
    heading.append(el('span', 'section-index', 'FIXED STATEMENTS / FIXED TACTIC BODIES'),
      el('span', invalid ? 'live-benchmark-state is-invalid' : stale ? 'live-benchmark-state is-stale' : 'live-benchmark-state',
        invalid ? `Invalid controls · comparison not certified${stale ? ' · stale run' : ''}` : !current ? 'Saved evidence · freshness unconfirmed' : recorded.state === 'running' ? 'Refresh running · previous report is stale' : stale ? 'Stale or unavailable evidence' : 'Complete for the observed revision'));
    container.append(heading);
    if (recorded.message) container.append(el('p', 'live-benchmark-message', recorded.message));
    if (recorded.freshness_reason) container.append(el('p', 'live-benchmark-message', recorded.freshness_reason));
    if (recorded.state === 'running' && recorded.total_rows > 0 && recorded.completed_rows !== undefined) {
      container.append(el('p', 'live-benchmark-progress', `Current refresh: ${recorded.completed_rows} / ${recorded.total_rows} measured rows. Scores below belong only to the last complete run.`));
    }
    if (!report) {
      container.append(empty('No completed strict benchmark report.', 'A successful worker, a manual theorem proof, or a legacy seed result does not fill this score table. Measured results appear after the runner completes and validates the fixed suite.'));
      return;
    }
    const metadata = el('dl', 'live-benchmark-metadata');
    const addMetadata = (label, value) => {
      const pair = el('div');
      pair.append(el('dt', '', label), el('dd', '', value));
      metadata.append(pair);
    };
    addMetadata('Completed run', report.run_id);
    addMetadata('Measured source revision', report.source_revision);
    addMetadata('Runner’s observed target revision', recorded.target_revision || 'Not reported · freshness unconfirmed');
    addMetadata('Runner last observed its target', recorded.observed_at ? `${dateTime(recorded.observed_at)} · ${relative(recorded.observed_at)}` : 'Not reported · freshness unconfirmed');
    addMetadata('Started / completed', `${dateTime(report.started_at)} / ${dateTime(report.completed_at)}`);
    addMetadata('Suite / scored denominator', `${report.suite.id} · ${report.suite.case_count} source cases`);
    if (report.toolchain?.pin) addMetadata('Pinned Lean toolchain', report.toolchain.pin);
    addMetadata('Suite SHA-256', report.suite.suite_sha256);
    addMetadata('Manifest / statement lock SHA-256', `${report.suite.manifest_sha256} / ${report.suite.lock_sha256}`);
    container.append(metadata);
    const revisionLink = link('Inspect the measured colony revision ↗', `${state.data.project.repo_url || ''}/commit/${report.source_revision}`);
    if (revisionLink) container.append(revisionLink);
    if (report.suite.scope) container.append(el('p', 'live-benchmark-selection', report.suite.scope));
    const selection = report.suite.selection || {};
    if (selection.kind || selection.policy) container.append(el('p', 'live-benchmark-selection', `${selection.kind ? pretty(selection.kind) + '. ' : ''}${selection.policy || ''}${selection.remaining_named_theorems !== undefined ? ` ${selection.remaining_named_theorems} other named upstream theorems are outside this sample.` : ''}`));
    container.append(el('p', 'live-benchmark-contract', `Strict Colony contract: exactly “by colony”, importing Colony.Tactic. No per-case manual steps, helpers or extra imports count as tactic wins. Each strategy gets ${report.protocol.timeout_seconds} seconds and ${report.protocol.max_heartbeats.toLocaleString()} heartbeats per case.`));
    const tableWrap = el('div', 'live-benchmark-table-wrap');
    const table = el('table', 'live-benchmark-table');
    const caption = el('caption', '', 'Completed scored cases · controls excluded');
    const header = el('tr');
    ['Strategy', 'Fixed proof body', 'Proved / cases', 'No proof', 'Timeout', 'Error', 'Total wall time'].forEach((label) => {
      const cell = el('th', '', label); cell.scope = 'col'; header.append(cell);
    });
    const thead = el('thead'); thead.append(header);
    const tbody = el('tbody');
    liveStrategies.forEach(([strategy, label]) => {
      const measured = report.summary[strategy];
      const row = el('tr', measured.valid ? '' : 'is-invalid');
      const name = el('th', '', label); name.scope = 'row'; row.append(name);
      const proof = el('td'); proof.append(el('code', '', report.protocol.proof_bodies[strategy])); row.append(proof);
      [measured.valid ? `${measured.proved} / ${measured.total}` : 'Not certified · invalid controls', measured.proof_failed, measured.timeouts, measured.errors, `${Number(measured.wall_seconds).toFixed(3)} s`]
        .forEach((value) => row.append(el('td', '', String(value))));
      tbody.append(row);
    });
    table.append(caption, thead, tbody); tableWrap.append(table); container.append(tableWrap);
    const comparison = report.baseline_comparability.blaster;
    container.append(el('p', 'live-benchmark-comparability', `Lean Blaster comparison: ${pretty(comparison.state)}. ${comparison.reason}`),
      el('p', 'live-benchmark-assurance', `${report.assurance.label}. Independent external replay: not performed. Freshness is relative to the runner’s last observed target; saved exports do not establish a live run.`));
    if (report.timing_note) container.append(el('p', 'live-benchmark-assurance', report.timing_note));
    if (report.assurance.security_boundary) container.append(el('p', 'live-benchmark-assurance', report.assurance.security_boundary));
    if (report.source_sha256 || report.runtime_source_sha256) {
      const hashes = el('details', 'live-generated-source');
      hashes.append(el('summary', '', 'Exact tactic and pinned evaluator input hashes'),
        el('pre', '', JSON.stringify({ source_sha256: report.source_sha256, runtime_source_sha256: report.runtime_source_sha256 }, null, 2)));
      container.append(hashes);
    }
    const cases = el('section', 'live-benchmark-cases');
    cases.append(el('h3', '', 'Original source cases'), el('p', '', 'Expand a theorem to inspect its unchanged statement, pinned provenance, exact proof bodies and all four measured outcomes.'));
    report.cases.forEach((item) => cases.append(liveCaseCard(item)));
    container.append(cases);
    const controls = el('section', 'live-benchmark-controls');
    controls.append(el('h3', '', 'Validity controls · excluded from the score'),
      el('p', '', 'Witnesses establish non-vacuity. An intentionally invalid theorem must fail; rejecting it is a control check, not a scored theorem win.'));
    report.controls.forEach((item) => controls.append(liveCaseCard(item, true)));
    if (!report.controls.length) controls.append(el('p', 'live-result-error', 'No validity controls were recorded in this report.'));
    container.append(controls);
  }

  function renderBenchmarks() {
    renderLiveBenchmark();
    const container = $('benchmark-list');
    container.replaceChildren();
    const reports = state.data.benchmarks;
    $('benchmark-controls').hidden = !reports.length;
    if (!reports.length) {
      const blank = el('div', 'benchmark-empty');
      blank.append(el('span', 'mini-label', 'NO BENCHMARK RESULTS RECORDED'), el('h3', '', 'The frontier is still ahead.'), el('p', '', 'There are no measured results in this state. Future reports should identify the exact problem, resource limits, toolchain, and proof checking method.'));
      container.append(blank);
      return;
    }
    const results = filteredBenchmarks(reports);
    const cards = el('div', 'benchmark-cards');
    results.forEach((result) => {
      const card = el('article', 'benchmark-card');
      const top = el('div', 'benchmark-card-top');
      const trust = trustFor(result);
      top.append(el('h3', '', result.name || result.title || result.benchmark || result.id || 'Recorded benchmark'), el('span', `trust-badge ${trust.className}`, trust.label));
      card.append(top);
      if (result.status) card.append(el('span', 'task-meta', pretty(result.status)));
      if (result.measured_at) card.append(el('span', 'task-meta', `Measured ${dateTime(result.measured_at)}`));
      const description = result.description || result.summary || result.property;
      if (description) card.append(el('p', '', printable(description)));
      const context = [result.track || result.family, result.kind, result.strategy].filter(Boolean).map(pretty);
      if (context.length) card.append(el('p', '', context.join(' / ')));
      const metrics = el('div', 'benchmark-values');
      const metricFields = [['elapsed_ms', 'ms total'], ['duration_ms', 'ms total'], ['wall_seconds', 's wall time'], ['kernel_check_ms', 'ms kernel check'], ['proof_bytes', 'proof bytes'], ['memory_mb', 'MB memory'], ['solved', 'solved'], ['total', 'total'], ['exit_code', 'exit code']];
      const added = new Set();
      metricFields.forEach(([key, label]) => {
        if (result[key] === undefined || result[key] === null || added.has(label)) return;
        const value = el('div');
        value.append(el('strong', '', printable(result[key])), el('span', '', label));
        metrics.append(value);
        added.add(label);
      });
      if (metrics.childElementCount) card.append(metrics);
      if (Array.isArray(result.axioms)) card.append(el('p', 'benchmark-assumptions', `Axioms: ${Array.isArray(result.axioms) ? result.axioms.length ? result.axioms.join(', ') : 'none (reported axiom-free)' : 'no axiom evidence produced'}`));
      if (result.independent_replay === false) card.append(el('p', 'benchmark-assumptions', 'Independent replay: not performed'));
      const artifact = link('Inspect evidence ↗', result.artifact_url || result.report_url || result.pr_url || result.url);
      if (artifact) card.append(artifact);
      const details = el('details');
      details.append(el('summary', '', 'Full recorded evidence'), el('pre', '', JSON.stringify(result, null, 2)));
      card.append(details);
      cards.append(card);
    });
    container.append(cards);
  }

  function filteredBenchmarks(reports) {
    const keyFor = (result) => string(result.run_key || '__unrecorded__');
    const strategyFor = (result) => string(result.strategy || '__unspecified__');
    const runs = new Map();
    reports.forEach((result) => {
      const key = keyFor(result);
      const at = validDate(result.measured_at)?.getTime() || 0;
      const existing = runs.get(key);
      if (!existing || at > existing.at) runs.set(key, { key, at, measured_at: result.measured_at, toolchain: result.toolchain });
    });
    const ordered = [...runs.values()].sort((a, b) => b.at - a.at || b.key.localeCompare(a.key));
    if (!state.benchmarkRunExplicit || !runs.has(state.benchmarkRun)) state.benchmarkRun = ordered[0].key;
    const runSelect = $('benchmark-run');
    const options = ordered.map((run, index) => {
      const raw = typeof run.toolchain === 'object' && run.toolchain ? run.toolchain.pin || run.toolchain.version || 'Unspecified toolchain' : run.toolchain || 'Unspecified toolchain';
      const toolchain = string(raw).replace(/^leanprover\/lean4:/, 'Lean ');
      const label = `${toolchain} · ${run.measured_at ? dateTime(run.measured_at) : 'Time not recorded'}${index === 0 ? ' · latest' : ''}`;
      return { key: run.key, label };
    });
    if (JSON.stringify([...runSelect.options].map((option) => ({ key: option.value, label: option.textContent }))) !== JSON.stringify(options)) {
      runSelect.replaceChildren();
      options.forEach((option) => runSelect.add(new Option(option.label, option.key)));
    }
    runSelect.value = state.benchmarkRun;
    runSelect.title = runSelect.selectedOptions[0]?.textContent || '';
    const runResults = reports.filter((result) => keyFor(result) === state.benchmarkRun);
    const strategies = [...new Set(runResults.map(strategyFor))].sort();
    const strategySelect = $('benchmark-strategy');
    const strategyOptions = [{ key: 'all', label: 'All strategies' }, ...strategies.map((strategy) => ({ key: strategy, label: strategy === '__unspecified__' ? 'Unspecified strategy' : pretty(strategy) }))];
    if (JSON.stringify([...strategySelect.options].map((option) => ({ key: option.value, label: option.textContent }))) !== JSON.stringify(strategyOptions)) {
      strategySelect.replaceChildren();
      strategyOptions.forEach((option) => strategySelect.add(new Option(option.label, option.key)));
    }
    if (state.benchmarkStrategy !== 'all' && !strategies.includes(state.benchmarkStrategy)) state.benchmarkStrategy = strategies.includes('colony') ? 'colony' : 'all';
    strategySelect.value = state.benchmarkStrategy;
    return runResults.filter((result) => state.benchmarkStrategy === 'all' || strategyFor(result) === state.benchmarkStrategy);
  }

  function renderReviews() {
    const reviews = state.data.reviews;
    $('review-count').textContent = `${reviews.length} recorded`;
    const list = $('reviews-list');
    list.replaceChildren();
    if (!reviews.length) {
      list.append(empty('No reviews recorded yet.', 'Review conclusions and their linked artifacts will appear here. A merged PR alone does not establish proof correctness.', '⌘'));
      return;
    }
    reviews.forEach((review) => {
      const card = el('article', 'review-card');
      const top = el('div', 'review-top');
      top.append(el('h3', '', review.title || review.task_id || review.id || 'Recorded review'), badge(review.status || review.verdict));
      card.append(top);
      if (review.summary || review.message) card.append(el('p', '', printable(review.summary || review.message)));
      card.append(el('span', 'task-meta', `Reviewer: ${string(review.reviewer || review.actor, 'Unspecified')}`));
      const artifact = link('Inspect review ↗', review.url || review.pr_url || review.artifact_url);
      if (artifact) card.append(artifact);
      list.append(card);
    });
  }

  function switchView(view, focus = false) {
    if (!['overview', 'queue', 'kanban', 'frontier', 'activity'].includes(view)) return;
    state.view = view;
    document.querySelectorAll('[role="tab"]').forEach((tab) => {
      const selected = tab.dataset.view === view;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    document.querySelectorAll('[role="tabpanel"]').forEach((panel) => { panel.hidden = panel.id !== `view-${view}`; });
    if (focus) $(`tab-${view}`).focus();
  }

  function detailSection(title, contents) {
    const section = el('section', 'detail-section');
    section.append(el('h3', '', title), contents);
    return section;
  }

  function renderDetails(kind, id, open = true) {
    const item = state.data[kind === 'task' ? 'tasks' : 'agents'].find((entry) => string(entry.id) === string(id));
    if (!item) return;
    state.selection = { kind, id };
    $('detail-kind').textContent = kind === 'task' ? 'RESEARCH TASK' : 'COLONY AGENT';
    $('detail-title').textContent = item.title || item.name || item.id || 'Details';
    const content = $('detail-content');
    content.replaceChildren(badge(item.status));
    if (item.description) content.append(el('p', 'detail-description', printable(item.description)));
    const properties = el('dl', 'detail-properties');
    const values = kind === 'task' ? [['Task ID', item.id], ['Role', roleLabel(item.role)], ['Owner', ownerFor(item)], ['Priority', pretty(item.priority)], ['Updated', dateTime(item.updated_at)], ['Lease until', item.lease_until ? dateTime(item.lease_until) : 'No active lease']] : [['Agent ID', item.id], ['Role', roleLabel(item.role)], ['Last seen', dateTime(item.last_seen)], ['Task', item.task_id || 'Unassigned']];
    values.forEach(([key, value]) => {
      const pair = el('div');
      pair.append(el('dt', '', key), el('dd', '', printable(value)));
      properties.append(pair);
    });
    content.append(properties);
    if (kind === 'task') {
      const recovery = recoveryDetails(item, cycleForTask(item));
      if (recovery) content.append(detailSection('Blocker recovery', recovery));
      const acceptance = item.acceptance;
      const criteria = Array.isArray(acceptance) ? acceptance : acceptance ? [acceptance] : [];
      if (criteria.length) {
        const list = el('ul');
        criteria.forEach((criterion) => list.append(el('li', '', printable(criterion))));
        content.append(detailSection('Acceptance criteria', list));
      } else content.append(detailSection('Acceptance criteria', el('p', '', 'No acceptance criteria recorded.')));
      if (item.summary) content.append(detailSection('Recorded outcome', el('p', '', printable(item.summary))));
      if (item.branch) content.append(detailSection('Branch', el('p', 'detail-json', item.branch)));
      if (Array.isArray(item.depends_on) && item.depends_on.length) {
        const deps = el('div', 'detail-links');
        item.depends_on.forEach((dependency) => {
          const task = state.data.tasks.find((entry) => entry.id === dependency);
          if (task) deps.append(taskButton(task)); else deps.append(el('span', 'task-meta', dependency));
        });
        content.append(detailSection('Depends on', deps));
      }
      const artifact = link('Inspect pull request ↗', item.pr_url, '');
      if (artifact) { const links = el('div', 'detail-links'); links.append(artifact); content.append(detailSection('Public evidence', links)); }
      const events = orderedEvents().filter((event) => event.task_id === item.id).slice(0, 4);
      if (events.length) { const log = el('div'); events.forEach((event) => log.append(eventRow(event))); content.append(detailSection('Recent task history', log)); }
    } else if (item.task_id) {
      const task = state.data.tasks.find((entry) => entry.id === item.task_id);
      if (task) { const assignment = el('div', 'detail-links'); assignment.append(taskButton(task)); content.append(detailSection('Current assignment', assignment)); }
    }
    if (open && !$('detail-dialog').open) $('detail-dialog').showModal();
  }

  document.addEventListener('click', (event) => {
    const task = event.target.closest('[data-task]');
    const agent = event.target.closest('[data-agent]');
    const tab = event.target.closest('[data-view]');
    const go = event.target.closest('[data-go]');
    if (task) renderDetails('task', task.dataset.task);
    else if (agent) renderDetails('agent', agent.dataset.agent);
    else if (tab) switchView(tab.dataset.view);
    else if (go) switchView(go.dataset.go, true);
  });
  document.querySelector('.tabs').addEventListener('keydown', (event) => {
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const index = tabs.indexOf(document.activeElement);
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    switchView(tabs[next].dataset.view, true);
  });
  $('kanban-search').addEventListener('input', renderKanban);
  $('kanban-role').addEventListener('change', renderKanban);
  $('task-search').addEventListener('input', renderQueue);
  $('task-status').addEventListener('change', renderQueue);
  $('event-kind').addEventListener('change', renderActivity);
  $('benchmark-run').addEventListener('change', () => {
    state.benchmarkRun = $('benchmark-run').value;
    state.benchmarkRunExplicit = true;
    renderBenchmarks();
  });
  $('benchmark-strategy').addEventListener('change', () => {
    state.benchmarkStrategy = $('benchmark-strategy').value;
    renderBenchmarks();
  });
  $('refresh').addEventListener('click', refresh);
  $('close-detail').addEventListener('click', () => $('detail-dialog').close());
  $('detail-dialog').addEventListener('close', () => { state.selection = null; });
  $('detail-dialog').addEventListener('click', (event) => {
    if (event.target !== $('detail-dialog')) return;
    const rect = $('detail-dialog').getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) $('detail-dialog').close();
  });
  switchView(window.location.hash.slice(1));
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 15000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
