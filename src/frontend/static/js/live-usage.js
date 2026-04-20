async function loadUsage() {
  const res = await fetch('/api/live-usage');
  const data = await res.json();

  const meta = document.getElementById('meta');
  const s = data.current_session || {};
  const w = data.current_week || {};

  document.getElementById('session-avail').textContent = s.available_percent == null ? '-' : s.available_percent + '% disponível';
  document.getElementById('session-used').textContent = s.used_percent == null ? '' : ('Usado: ' + s.used_percent + '%');
  document.getElementById('session-reset').textContent = s.resets_at ? ('Renova: ' + s.resets_at) : '';

  document.getElementById('week-avail').textContent = w.available_percent == null ? '-' : w.available_percent + '% disponível';
  document.getElementById('week-used').textContent = w.used_percent == null ? '' : ('Usado: ' + w.used_percent + '%');
  document.getElementById('week-reset').textContent = w.resets_at ? ('Renova: ' + w.resets_at) : '';

  document.getElementById('raw').textContent = data.raw_excerpt || '';
  document.getElementById('error').textContent = data.error || '';
  meta.textContent = 'Última captura: ' + (data.captured_at || '-') + (data.ok ? '' : ' (falha ao interpretar)');
}

function reloadNow(){ loadUsage().catch(console.error); }
setInterval(() => loadUsage().catch(console.error), 30000);
loadUsage().catch(console.error);
