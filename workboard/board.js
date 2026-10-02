(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const titles = { decision: 'Decision needed', working: 'Working', checking: 'Checking',
    blocked: 'Blocked', queued: 'Queued' };
  const requestTitles = { saved: 'Saved', queued: 'Queued', received: 'Received',
    working: 'Working', done: 'Done', blocked: 'Blocked' };
  const sessionId = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
  let board = null;
  let selected = null;
  let loading = false;
  let renderPending = false;
  let generalDraft = { owner: '', message: '', attempt: null };
  const taskDrafts = new Map();
  const seen = new Map();
  try {
    const saved = JSON.parse(localStorage.getItem('samepage-workboard-seen-v1') || '{}');
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
      for (const [key, signature] of Object.entries(saved)) {
        if (typeof signature === 'string') seen.set(key, signature);
      }
    }
  } catch { /* Private browsing can refuse local storage. */ }

  function node(tag, className, value) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined) element.textContent = String(value);
    return element;
  }
  function age(value) {
    const time = Date.parse(value || '');
    if (!Number.isFinite(time)) return 'time unknown';
    const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000));
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
    return `${Math.floor(minutes / 1440)}d ago`;
  }
  function key(item) { return `${item.owner_session}/${item.id}`; }
  function safeUrl(value) {
    if (typeof value !== 'string') return null;
    const raw = value.trim();
    if (!raw || raw.startsWith('//') || raw.includes('\\') ||
        (!raw.startsWith('/') && !/^https?:\/\//i.test(raw))) return null;
    try {
      const url = new URL(raw, location.origin);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url : null;
    } catch { return null; }
  }
  function link(parent, label, address) {
    const url = safeUrl(address);
    if (!url) return false;
    const anchor = node('a', '', label);
    anchor.href = url.href;
    if (url.origin !== location.origin) {
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      anchor.setAttribute('aria-label', `${label} (opens in a new tab)`);
    }
    parent.append(anchor);
    return true;
  }
  function sessionName(id) {
    const found = board && board.sessions.find((entry) => entry.id === id);
    return found ? found.label : id;
  }
  function currentFilter() {
    const raw = location.hash.match(/^#session\/([^/]+)$/);
    if (!raw) return null;
    try {
      const id = decodeURIComponent(raw[1]);
      return sessionId.test(id) ? id : null;
    } catch { return null; }
  }
  function currentItem() {
    const raw = location.hash.match(/^#task\/([^/]+)\/([^/]+)$/);
    if (!raw || !board) return null;
    try {
      const owner = decodeURIComponent(raw[1]);
      const id = decodeURIComponent(raw[2]);
      return board.items.find((item) => item.owner_session === owner && item.id === id) || null;
    } catch { return null; }
  }
  function taskHash(item) {
    return `#task/${encodeURIComponent(item.owner_session)}/${encodeURIComponent(item.id)}`;
  }
  function reviewUrl(item) { return safeUrl(item.preview_url) ? item.preview_url : null; }
  function signature(item) { return JSON.stringify([item.version || '', reviewUrl(item)]); }
  function unread(item) { return reviewUrl(item) && seen.get(key(item)) !== signature(item); }
  function markSeen(item) {
    seen.set(key(item), signature(item));
    try { localStorage.setItem('samepage-workboard-seen-v1', JSON.stringify(Object.fromEntries(seen))); }
    catch { /* The mark is still kept for this page visit. */ }
    render();
  }
  function badge(state) { return node('span', `badge ${state}`, titles[state] || state); }

  function renderSessions() {
    const container = $('sessions');
    if (!board || !board.sessions.length) {
      container.replaceChildren(node('p', 'muted', 'No session report yet.'));
      return;
    }
    container.replaceChildren(...board.sessions.map((session) => {
      const jobs = board.items.filter((item) => item.owner_session === session.id ||
        (Array.isArray(item.workers) && item.workers.includes(session.id)));
      const stale = !session.has_report || session.stale;
      let activity = 'Update needed';
      let note = session.has_report ? 'The last report may no longer describe current work.' :
        'Waiting for this session to report.';
      if (!stale && session.activity && typeof session.activity.state === 'string') {
        activity = session.activity.state[0].toUpperCase() + session.activity.state.slice(1) + ' (reported)';
        note = session.activity.note || 'No activity note supplied.';
      } else if (!stale && jobs.some((item) => ['working', 'checking'].includes(item.state))) {
        activity = 'Work reported';
        note = 'The owner has not reported current session activity.';
      }
      const card = node('article', `session${session.stale ? ' stale' : ''}${!session.has_report ? ' missing' : ''}`);
      const top = node('div', 'session-top');
      const name = node('a', 'session-name', session.label || session.id);
      name.href = `#session/${encodeURIComponent(session.id)}`;
      top.append(name, node('span', 'badge', activity));
      card.append(top, node('p', '', note), node('small', '',
        `${session.id} · ${jobs.length} open · ${session.has_report ? 'Reported ' + age(session.updated_at) : 'No report'}`));
      return card;
    }));
  }

  function renderRequests() {
    const requests = board ? board.requests : [];
    $('requests-section').hidden = !requests.length;
    $('requests-count').textContent = `${requests.length} unfinished`;
    $('requests').replaceChildren(...requests.map((request) => {
      const card = node('article', 'request');
      card.append(node('span', 'badge', requestTitles[request.status] || 'Status unknown'),
        node('span', 'request-meta', `${sessionName(request.owner_session)} · ${age(request.updated_at || request.created_at)}`),
        node('p', '', request.message));
      if (typeof request.note === 'string' && request.note) card.append(node('p', 'request-note', request.note));
      return card;
    }));
  }

  function renderGeneral() {
    const picker = $('general-owner');
    const previous = generalDraft.owner;
    picker.replaceChildren(node('option', '', 'Choose a session'));
    picker.firstChild.value = '';
    if (board) for (const session of board.sessions) {
      const option = node('option', '', `${session.label} (${session.id})`);
      option.value = session.id;
      picker.append(option);
    }
    picker.value = board && board.sessions.some((session) => session.id === previous) ? previous : '';
    generalDraft.owner = picker.value;
    $('general-message').value = generalDraft.message;
    $('general-form').querySelector('button').disabled = !board || !board.sessions.length;
  }

  function renderCard(item) {
    const card = node('article', 'item');
    const title = node('a', 'item-title', item.title);
    title.href = taskHash(item);
    card.append(title, badge(item.state), node('p', '', item.summary),
      node('small', 'item-meta', `${sessionName(item.owner_session)} · ${age(item.updated_at)}${unread(item) ? ' · New review' : ''}`));
    return card;
  }
  function renderOverview() {
    const filter = currentFilter();
    const nav = $('filter');
    nav.hidden = !filter;
    if (filter) {
      const all = node('a', '', 'All work'); all.href = '#overview';
      nav.replaceChildren(node('span', '', `Showing ${sessionName(filter)}`), all);
    }
    const items = board ? board.items.filter((item) => !filter || item.owner_session === filter ||
      (Array.isArray(item.workers) && item.workers.includes(filter))) : [];
    for (const [id, selectedItems] of [
      ['decisions', items.filter((item) => item.state === 'decision')],
      ['active', items.filter((item) => ['working', 'checking'].includes(item.state))],
      ['waiting', items.filter((item) => ['queued', 'blocked'].includes(item.state))],
    ]) {
      $(id + '-count').textContent = `${selectedItems.length}`;
      $(id).replaceChildren(...(selectedItems.length ? selectedItems.map(renderCard) :
        [node('p', 'empty', id === 'decisions' ? 'No decision waiting.' : id === 'active' ?
          'No active work reported.' : 'Nothing waiting or queued.') ]));
    }
  }

  function renderDetail() {
    const item = currentItem();
    const form = $('task-form');
    $('detail').hidden = !location.hash.startsWith('#task/');
    $('overview').hidden = !$('detail').hidden;
    form.dataset.ownerSession = item && !$('detail').hidden ? item.owner_session : '';
    form.dataset.taskId = item && !$('detail').hidden ? item.id : '';
    if ($('detail').hidden) return;
    const body = $('detail-body');
    form.hidden = !item;
    if (!item) {
      body.replaceChildren(node('h2', '', 'This item is no longer open'),
        node('p', 'muted', 'The owner may have completed it or refreshed the report.'));
      return;
    }
    selected = key(item);
    const heading = node('h2', '', item.title); heading.id = 'detail-title';
    const meta = node('p', 'detail-meta', `${sessionName(item.owner_session)} · ${item.version || 'No version'} · ${item.source} · Reported ${age(item.updated_at)}`);
    body.replaceChildren(heading, meta, badge(item.state), node('p', '', item.summary));
    if (item.detail) body.append(node('p', '', item.detail));
    if (item.decision) body.append(node('p', 'detail-label', 'Decision needed'), node('p', 'detail-note', item.decision));
    body.append(node('p', 'detail-label', 'Next'), node('p', '', item.next));
    const links = node('div', 'links');
    if (item.url) link(links, 'Open related link', item.url);
    if (Array.isArray(item.links)) for (const entry of item.links) link(links, entry.label, entry.url);
    if (links.childNodes.length) body.append(links);
    if (reviewUrl(item)) {
      const review = node('div', 'review');
      review.append(node('strong', '', item.version ? `Review ${item.version}` : 'Available review'));
      const row = node('div', 'links');
      link(row, 'Open review', item.preview_url);
      review.append(row);
      const seenButton = node('button', '', unread(item) ? 'Mark as seen' : 'Seen');
      seenButton.type = 'button'; seenButton.disabled = !unread(item);
      seenButton.addEventListener('click', () => markSeen(item));
      review.append(seenButton, node('p', 'request-note', 'Seen does not mean approved. Send a decision separately.'));
      body.append(review);
    }
    const draft = taskDrafts.get(selected) || { message: '', attempt: null };
    taskDrafts.set(selected, draft);
    $('task-message').value = draft.message;
    $('task-feedback').textContent = draft.feedback || '';
  }

  function render() {
    renderSessions(); renderRequests(); renderGeneral(); renderOverview(); renderDetail();
    $('warning').hidden = !board || !board.warnings.length;
    $('warning').textContent = board && board.warnings.length ? board.warnings.join(' ') : '';
    renderPending = false;
  }

  function interactiveFocus() {
    const active = document.activeElement;
    return active && active.matches('a, button, input, select, textarea, summary, [tabindex], [contenteditable="true"]');
  }

  async function refresh() {
    if (loading) return;
    loading = true;
    try {
      const response = await fetch('/api/workboard', { cache: 'no-store', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const data = await response.json();
      if (!data || !Array.isArray(data.items) || !Array.isArray(data.sessions) ||
          !Array.isArray(data.warnings) || !Array.isArray(data.requests) ||
          typeof data.csrf_token !== 'string') throw new Error('The board response is incomplete');
      const hadBoard = Boolean(board);
      board = data;
      $('freshness').textContent = `Checked ${age(data.generated_at)} · Source: samepage WIP`;
      $('error').hidden = true;
      if (hadBoard && interactiveFocus()) renderPending = true;
      else render();
    } catch (error) {
      $('error').hidden = false;
      $('error').textContent = `Could not refresh Workboard. ${error instanceof Error ? error.message : 'Try again shortly.'}`;
      $('freshness').textContent = 'Last report state may be stale';
    } finally { loading = false; }
  }

  async function send(kind, event) {
    event.preventDefault();
    if (!board || !board.csrf_token) return;
    const item = kind === 'task' ? currentItem() : null;
    const form = $(kind + '-form');
    const feedback = $(kind + '-feedback');
    if (kind === 'task' && (form.hidden || !item ||
        form.dataset.ownerSession !== item.owner_session || form.dataset.taskId !== item.id)) {
      feedback.textContent = 'This item changed or is no longer open. Your instruction is kept. Open the current item before sending.';
      return;
    }
    const draft = item ? taskDrafts.get(key(item)) : generalDraft;
    const input = $(kind + '-message');
    const rawMessage = input.value;
    const owner = item ? item.owner_session : $('general-owner').value;
    const message = rawMessage.trim();
    if (!draft || !owner || !message) { feedback.textContent = 'Choose a session and write an instruction.'; return; }
    draft.message = rawMessage;
    if (!item) generalDraft.owner = owner;
    const target = `${owner}/${item ? item.id : ''}`;
    if (!draft.attempt || draft.attempt.message !== message || draft.attempt.target !== target) {
      if (!crypto.randomUUID) { feedback.textContent = 'Secure request IDs are unavailable in this browser.'; return; }
      draft.attempt = { id: crypto.randomUUID(), message, target };
    }
    const payload = { id: draft.attempt.id, owner_session: owner, message };
    if (item) payload.task_id = item.id;
    const submitted = { owner, target, rawMessage, attemptId: payload.id,
      itemKey: item ? key(item) : null };
    const button = form.querySelector('button');
    button.disabled = true;
    feedback.textContent = 'Saving…';
    try {
      const response = await fetch('/api/requests', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Workboard-Token': board.csrf_token },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : `Server returned ${response.status}`);
      if (!data.request || data.request.id !== payload.id || data.request.owner_session !== owner ||
          data.request.task_id !== (item ? item.id : null)) throw new Error('The save was not confirmed for this owner');
      const visibleItem = item ? currentItem() : null;
      const sameVisibleTarget = item ? visibleItem && key(visibleItem) === submitted.itemKey :
        $('general-owner').value === submitted.owner && generalDraft.owner === submitted.owner;
      const sameDraft = draft.message === submitted.rawMessage &&
        draft.attempt && draft.attempt.id === submitted.attemptId &&
        draft.attempt.target === submitted.target;
      const clearSubmittedDraft = sameVisibleTarget && sameDraft && input.value === submitted.rawMessage;
      if (clearSubmittedDraft) {
        draft.message = ''; draft.attempt = null;
        input.value = '';
      }
      draft.feedback = clearSubmittedDraft ?
        'Saved in samepage. The agent must pick it up and acknowledge it.' :
        'Previous instruction saved in samepage. Your current draft is kept.';
      if (!item || sameVisibleTarget) feedback.textContent = draft.feedback;
      board.requests = board.requests.filter((entry) => entry.id !== data.request.id);
      board.requests.unshift(data.request);
      renderRequests();
    } catch (error) {
      feedback.textContent = `Could not confirm the save. ${error instanceof Error ? error.message : ''} Your text is kept. Retry safely.`;
    } finally { button.disabled = false; }
  }

  $('general-owner').addEventListener('change', (event) => { generalDraft.owner = event.target.value; });
  $('general-message').addEventListener('input', (event) => { generalDraft.message = event.target.value; });
  $('task-message').addEventListener('input', (event) => {
    if (selected && taskDrafts.has(selected)) taskDrafts.get(selected).message = event.target.value;
  });
  $('general-form').addEventListener('submit', (event) => { void send('general', event); });
  $('task-form').addEventListener('submit', (event) => { void send('task', event); });
  window.addEventListener('hashchange', render);
  document.addEventListener('focusout', () => {
    setTimeout(() => { if (renderPending && !interactiveFocus()) render(); }, 0);
  });
  void refresh();
  setInterval(() => { void refresh(); }, 10_000);
})();
