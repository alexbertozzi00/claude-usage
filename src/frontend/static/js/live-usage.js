const PROVIDER_STORAGE_KEY = 'live_usage_provider';

function getSelectedProvider() {
  const select = document.getElementById('provider-select');
  return (select && select.value) ? select.value : 'claude';
}

function setProvider(provider) {
  const select = document.getElementById('provider-select');
  if (select) {
    select.value = provider || 'claude';
  }
}

function restoreProviderPreference() {
  try {
    const stored = localStorage.getItem(PROVIDER_STORAGE_KEY);
    if (stored === 'claude' || stored === 'codex') {
      setProvider(stored);
    }
  } catch (e) {
    console.warn('Falha ao restaurar provider', e);
  }
}

function persistProviderPreference(provider) {
  try {
    localStorage.setItem(PROVIDER_STORAGE_KEY, provider);
  } catch (e) {
    console.warn('Falha ao persistir provider', e);
  }
}

async function loadUsage() {
  const provider = getSelectedProvider();
  const res = await fetch('/api/live-usage?provider=' + encodeURIComponent(provider));
  const data = await res.json();

  const meta = document.getElementById('meta');
  const validation = data.validation || {};
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
  meta.textContent = '[' + ((data.provider || provider).toUpperCase()) + '] Última captura: ' + (data.captured_at || '-') + (data.ok ? '' : ' (falha ao interpretar)');
  document.getElementById('validation').textContent =
    'Validação: session=' + (validation.has_current_session ? 'ok' : 'n/a') +
    ' | week=' + (validation.has_current_week ? 'ok' : 'n/a') +
    ' | linhas=' + (validation.line_count == null ? '-' : validation.line_count);
}

function onProviderChange() {
  const provider = getSelectedProvider();
  persistProviderPreference(provider);
  reloadNow();
}

function reloadNow(){ loadUsage().catch(console.error); }
restoreProviderPreference();
setInterval(() => loadUsage().catch(console.error), 30000);
loadUsage().catch(console.error);
