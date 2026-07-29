'use strict';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function extractSummary(entry) {
  const d = entry.data || {};
  if (d.topic)              return d.topic;
  if (d.url)                return d.url;
  if (d.file_path)          return d.file_path;
  if (d.score !== undefined) return `Score: ${d.score}%`;
  if (d.quiz_id)            return `Quiz ${String(d.quiz_id).slice(0, 8)}…`;
  return entry.activity_type;
}

function computeStats(history) {
  const topics = new Set();
  const scores = [];
  const scoresByTopic = {};

  for (const entry of history) {
    const d = entry.data || {};
    if (d.topic)    topics.add(d.topic);
    if (d.url)      topics.add(d.url);
    if (d.score !== undefined) {
      scores.push(Number(d.score));
      const key = d.topic || 'Unknown';
      (scoresByTopic[key] = scoresByTopic[key] || []).push(Number(d.score));
    }
  }

  const avgByTopic = Object.entries(scoresByTopic).map(([topic, s]) => ({
    topic,
    avg: s.reduce((a, b) => a + b, 0) / s.length,
  }));

  avgByTopic.sort((a, b) => b.avg - a.avg);

  const best  = avgByTopic[0]?.topic ?? '—';
  const worst = avgByTopic[avgByTopic.length - 1]?.topic ?? '—';
  const avgScore = scores.length
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
    : null;

  return { topicsCount: topics.size, avgScore, best, worst };
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function renderStats(stats) {
  document.getElementById('topics-count').textContent = stats.topicsCount || '—';
  document.getElementById('avg-score').textContent =
    stats.avgScore !== null ? `${stats.avgScore}%` : '—';
  document.getElementById('best-topic').textContent  = stats.best;
  document.getElementById('worst-topic').textContent = stats.worst;
}

function renderActivities(history, listEl) {
  const recent = [...history].reverse().slice(0, 20); // newest first, max 20

  for (const entry of recent) {
    const li = document.createElement('li');
    li.classList.add('activity-item');

    const badge = document.createElement('span');
    badge.classList.add('activity-type');
    badge.textContent = entry.activity_type.replace(/_/g, ' ');

    const summary = document.createElement('span');
    summary.classList.add('activity-summary');
    summary.title = extractSummary(entry); // full text on hover
    summary.textContent = extractSummary(entry);

    const ts = document.createElement('span');
    ts.classList.add('activity-timestamp');
    ts.textContent = formatTimestamp(entry.timestamp);

    li.appendChild(badge);
    li.appendChild(summary);
    li.appendChild(ts);
    listEl.appendChild(li);
  }
}

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------

async function loadProgress() {
  const listEl   = document.getElementById('activity-list');
  const emptyEl  = document.getElementById('empty-state');

  let history = [];

  try {
    const res = await fetch('/api/progress/default_user');

    if (res.status === 404) {
      emptyEl.classList.remove('hidden');
      return;
    }

    if (!res.ok) {
      emptyEl.textContent = 'Could not load progress data. Please try again later.';
      emptyEl.classList.remove('hidden');
      return;
    }

    const data = await res.json();
    history = Array.isArray(data.history) ? data.history : [];
  } catch (err) {
    emptyEl.textContent = `Network error: ${err.message}`;
    emptyEl.classList.remove('hidden');
    return;
  }

  if (history.length === 0) {
    emptyEl.classList.remove('hidden');
    return;
  }

  renderStats(computeStats(history));
  renderActivities(history, listEl);
}

document.addEventListener('DOMContentLoaded', loadProgress);
