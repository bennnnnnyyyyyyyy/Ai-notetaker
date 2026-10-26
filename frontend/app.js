const state = { meetings: [], campaigns: [] };

const $ = (id) => document.getElementById(id);

let currentMeetingId = null;

function showView(name) {
  state.currentView = name;
  if (name !== 'meeting-detail') currentMeetingId = null;
  document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
  const view = $(`view-${name}`);
  if (view) view.classList.add('active');
  document.querySelectorAll('.nav-link').forEach((link) => {
    link.classList.toggle('active', link.dataset.view === name);
  });
}

async function api(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* plain error */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function meetingCard(meeting) {
  const date = meeting.created_at ? new Date(meeting.created_at).toLocaleString() : '';
  return `<button class="meeting-card" aria-label="Open ${escapeHtml(meeting.meeting_type)} meeting, status ${escapeHtml(meeting.status)}" data-meeting-id="${meeting.id}">
    <div><strong>${escapeHtml(meeting.meeting_type)}</strong><span class="status status-${meeting.status}">${escapeHtml(meeting.status)}</span></div>
    <div class="muted">${escapeHtml(meeting.url)}</div><div class="muted">${escapeHtml(date)}</div>
  </button>`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

async function loadMeetings() {
  state.meetings = await api('/meetings');
  $('meetings-list').innerHTML = state.meetings.length
    ? state.meetings.map(meetingCard).join('')
    : '<p class="muted">No meetings registered yet.</p>';
  $('recent-meetings').innerHTML = state.meetings.slice(0, 5).map(meetingCard).join('') || '<p class="muted">No meetings yet.</p>';
  $('stat-total').textContent = state.meetings.length;
  $('stat-processing').textContent = state.meetings.filter((m) => ['joining', 'recording', 'processing'].includes(m.status)).length;
  $('stat-completed').textContent = state.meetings.filter((m) => m.status === 'completed').length;
  $('stat-failed').textContent = state.meetings.filter((m) => m.status === 'failed').length;
}

async function loadCampaigns() {
  state.campaigns = await api('/campaigns');
  $('campaigns-list').innerHTML = state.campaigns.length
    ? state.campaigns.map((c) => `<div class="meeting-card"><strong>${escapeHtml(c.name)}</strong><div class="muted">v${escapeHtml(c.config_version)} · ${escapeHtml(c.config_path)}</div></div>`).join('')
    : '<p class="muted">No campaigns configured.</p>';
  $('f-campaign').innerHTML = '<option value="">— None —</option>' + state.campaigns.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
}

async function loadReadiness() {
  const result = await api('/system/readiness');
  const rows = Object.entries(result.checks).map(([name, check]) => {
    const label = name.replaceAll('_', ' ');
    return `<div class="readiness-row"><span>${escapeHtml(label)}</span><span class="status status-${check.status}">${escapeHtml(check.status)}</span><small>${escapeHtml(check.detail || '')}</small></div>`;
  }).join('');
  $('readiness').innerHTML = `<div class="readiness-summary">Overall: <strong>${escapeHtml(result.status)}</strong></div>${rows}`;
}

async function openMeeting(id) {
  currentMeetingId = id;
  const meeting = await api(`/meetings/${id}`);
  $('detail-content').innerHTML = `<h1>Meeting</h1><div class="form-card">
    <p><strong>Type:</strong> ${escapeHtml(meeting.meeting_type)}</p>
    <p role="status" aria-live="polite"><strong>Status:</strong> <span class="status status-${meeting.status}">${escapeHtml(meeting.status)}</span></p>
    <p><strong>URL:</strong> <a href="${escapeHtml(meeting.url)}" target="_blank" rel="noopener">${escapeHtml(meeting.url)}</a></p>
    ${meeting.error_message ? `<p class="form-error">${escapeHtml(meeting.error_message)}</p>` : ''}
    ${['pending', 'failed'].includes(meeting.status) ? `<button class="btn-primary" id="start-${meeting.id}">Start capture</button>` : ''}
  </div>`;
  const start = $(`start-${meeting.id}`);
  if (start) start.onclick = async () => { await api(`/meetings/${meeting.id}/start-capture`, { method: 'POST' }); await loadMeetings(); await openMeeting(meeting.id); };
  showView('meeting-detail');
}

document.querySelectorAll('.nav-link').forEach((link) => link.addEventListener('click', async (event) => {
  event.preventDefault(); showView(link.dataset.view);
  if (link.dataset.view === 'dashboard' || link.dataset.view === 'meetings') await loadMeetings();
  if (link.dataset.view === 'campaigns') await loadCampaigns();
}));

document.addEventListener('click', (event) => {
  const card = event.target.closest('[data-meeting-id]');
  if (card) openMeeting(card.dataset.meetingId).catch((error) => alert(error.message));
});

$('back-btn').onclick = () => showView('meetings');
$('refresh-readiness').onclick = () => loadReadiness().catch((error) => { $('readiness').textContent = error.message; });
$('setup-browser-btn').onclick = async () => {
  $('readiness').textContent = 'Opening Chrome with capture profile…';
  try {
    const result = await api('/system/setup-browser', { method: 'POST' });
    $('readiness').textContent = result.detail;
  } catch (error) {
    $('readiness').textContent = error.message;
  }
};
$('new-meeting-form').onsubmit = async (event) => {
  event.preventDefault(); $('form-error').classList.add('hidden');
  const scheduled = $('f-scheduled').value;
  try {
    const meeting = await api('/meetings', { method: 'POST', body: JSON.stringify({
      url: $('f-url').value.trim(), meeting_type: $('f-type').value,
      campaign_id: $('f-campaign').value || null, opener_name: $('f-opener').value.trim() || null,
      closer_name: $('f-closer').value.trim() || null, scheduled_at: scheduled ? new Date(scheduled).toISOString() : null,
      pre_booking_notes: $('f-notes').value.trim() || null,
    }) });
    await api(`/meetings/${meeting.id}/start-capture`, { method: 'POST' });
    event.target.reset(); await loadMeetings(); await openMeeting(meeting.id);
  } catch (error) { $('form-error').textContent = error.message; $('form-error').classList.remove('hidden'); }
};

Promise.all([loadMeetings(), loadCampaigns(), loadReadiness()]).catch((error) => { $('recent-meetings').innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`; });

setInterval(async () => {
  const hasActive = state.meetings.some((meeting) => ['joining', 'waiting_for_admission', 'recording', 'processing'].includes(meeting.status));
  if (hasActive || currentMeetingId) {
    await loadMeetings().catch(() => {});
    if (currentMeetingId && state.currentView === 'meeting-detail') {
      const meeting = await api(`/meetings/${currentMeetingId}`).catch(() => null);
      if (meeting) {
        $('detail-content').innerHTML = `<h1>Meeting</h1><div class="form-card">
          <p><strong>Type:</strong> ${escapeHtml(meeting.meeting_type)}</p>
          <p role="status" aria-live="polite"><strong>Status:</strong> <span class="status status-${meeting.status}">${escapeHtml(meeting.status)}</span></p>
          <p><strong>URL:</strong> <a href="${escapeHtml(meeting.url)}" target="_blank" rel="noopener">${escapeHtml(meeting.url)}</a></p>
          ${meeting.error_message ? `<p class="form-error">${escapeHtml(meeting.error_message)}</p>` : ''}
          ${['pending', 'failed'].includes(meeting.status) ? `<button class="btn-primary" id="start-${meeting.id}">Start capture</button>` : ''}
        </div>`;
        const start = $(`start-${meeting.id}`);
        if (start) start.onclick = async () => { await api(`/meetings/${meeting.id}/start-capture`, { method: 'POST' }); await loadMeetings(); await openMeeting(meeting.id); };
      }
    }
  }
}, 2000);
