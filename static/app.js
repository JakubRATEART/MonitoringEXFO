const API_STATUS = '/api/status';
const API_ACK = '/api/acknowledge';
const API_REFRESH = '/api/refresh';

async function fetchStatus() {
  const res = await fetch(API_STATUS);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

function makeCard(device) {
  const col = document.createElement('div');
  col.className = 'card-item';
  col.setAttribute('data-model', device.model);

  const card = document.createElement('div');
  card.className = 'card h-100';

  // 24h Blue glow for newly detected update
  if (device.is_new_update_24h) {
    card.classList.add('card--new-update');
  } else if (!device.detected_version) {
    card.classList.add('card--unknown');
  } else if (device.changed) {
    card.classList.add('card--outdated');
  }

  // Make only the header clickable for URL
  const header = document.createElement('div');
  header.className = 'card-header clickable';
  header.onclick = () => window.open(device.url, '_blank');

  const body = document.createElement('div');
  body.className = 'card-body';

  const titleRow = document.createElement('div');
  titleRow.className = 'd-flex justify-content-between align-items-start';

  const title = document.createElement('h5');
  title.className = 'card-title mb-0';
  title.innerText = device.model;

  header.appendChild(titleRow);
  card.appendChild(header);

  const statusDot = document.createElement('span');
  statusDot.className = 'status-dot';
  if (device.is_new_update_24h) {
    statusDot.classList.add('status-dot--blue');
  } else if (!device.detected_version) {
    statusDot.classList.add('status-dot--orange');
  } else {
    statusDot.classList.add(device.changed ? 'status-dot--red' : 'status-dot--green');
  }

  titleRow.appendChild(title);
  titleRow.appendChild(statusDot);

  const category = document.createElement('div');
  category.className = 'text-muted small mb-2 category';
  category.innerText = device.category || '';

  const versionsContainer = document.createElement('div');
  versionsContainer.className = 'version-container';

  const stored = document.createElement('div');
  stored.className = 'version-info';
  stored.innerHTML = `<strong>Zapisana:</strong> ${
    device.stored_version
      ? `<span class="version-value stored-version">${device.stored_version}</span>`
      : '<span class="version-none stored-version">brak</span>'
  }`;

  const detected = document.createElement('div');
  detected.className = 'version-info';
  detected.innerHTML = `<strong>Wykryta:</strong> ${
    device.detected_version
      ? `<span class="version-value detected-version">${device.detected_version}</span>`
      : '<span class="version-none detected-version">nieznana</span>'
  }`;

  if (device.is_new_update_24h) {
    const newBadge = document.createElement('div');
    newBadge.className = 'badge-new-update';
    newBadge.innerText = 'Nowa wersja (<24h)';
    detected.appendChild(newBadge);
  }

  if (device.update_info) {
    const updateInfo = document.createElement('div');
    updateInfo.className = 'alert alert-warning mt-2 mb-0 py-1 px-2 small update-info';
    updateInfo.innerHTML = device.update_info;
    detected.appendChild(updateInfo);
  }

  const dates = document.createElement('div');
  dates.className = 'text-muted small mt-2';
  dates.innerHTML = `<strong>Kiedy zapisano?</strong> <span class="stored-date">${device.stored_release_date || '-'}</span><br><strong>kiedy zapisano?</strong> <span class="detected-date">${device.detected_release_date || '-'}</span>`;

  const btnGroup = document.createElement('div');
  btnGroup.className = 'mt-3 d-flex gap-2';

  const ackBtn = document.createElement('button');
  ackBtn.className = 'btn btn-sm btn-outline-success ack-btn';
  ackBtn.innerText = 'Acknowledge';
  ackBtn.disabled = !device.changed;
  ackBtn.onclick = async () => {
    ackBtn.disabled = true;
    try {
      const r = await fetch(API_ACK, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          model: device.model,
          version: device.detected_version
        })
      });
      if (!r.ok) throw new Error('ack failed');
      await refreshAndRender();
    } catch (e) {
      console.error(e);
      alert('Zatwierdzanie nie powiodło się');
    } finally {
      ackBtn.disabled = false;
    }
  };

  btnGroup.appendChild(ackBtn);

  body.appendChild(category);
  versionsContainer.appendChild(stored);
  versionsContainer.appendChild(detected);
  body.appendChild(versionsContainer);
  body.appendChild(dates);
  body.appendChild(btnGroup);

  card.appendChild(body);
  col.appendChild(card);
  return col;
}

// Simple loader overlay control (creates overlay element once)
function showLoader() {
  let overlay = document.getElementById('loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.innerHTML = `<div class="loader-inner"><div class="spinner"></div><div class="loader-text">Ładowanie…</div></div>`;
    document.body.appendChild(overlay);
  }
  overlay.classList.add('visible');
  try {
    const cards = document.querySelectorAll('#cards .card');
    const dots = document.querySelectorAll('#cards .status-dot');
    cards.forEach(c => c.classList.add('card--loading'));
    dots.forEach(d => {
      d.classList.remove('status-dot--red', 'status-dot--green', 'status-dot--orange', 'status-dot--blue');
      d.classList.add('status-dot--orange');
    });
  } catch (e) {
    console.warn('showLoader: could not add loading class to cards', e);
  }
}

function hideLoader() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('visible');
  try {
    const cards = document.querySelectorAll('#cards .card');
    cards.forEach(c => c.classList.remove('card--loading'));
    const data = window.__lastDevices || [];
    if (Array.isArray(data) && data.length > 0) {
      renderDevices(data);
      updateStatusBar(data);
    }
  } catch (e) {
    console.warn('hideLoader: could not remove loading class from cards', e);
  }
}

// Render devices in-place: update existing cards when possible to avoid flicker
function renderDevices(devices) {
  const container = document.getElementById('cards');
  if (!container) return;

  const seen = new Set();
  devices.forEach(device => {
    seen.add(device.model);
    const selector = `[data-model="${device.model}"]`;
    const existing = container.querySelector(selector);
    if (existing) {
      // Remove any deprecated store-btn if still present
      const oldStoreBtn = existing.querySelector('.store-btn');
      if (oldStoreBtn) oldStoreBtn.remove();

      // update fields
      const title = existing.querySelector('.card-title');
      if (title) title.textContent = device.model;

      const statusDot = existing.querySelector('.status-dot');
      if (statusDot) {
        statusDot.classList.remove('status-dot--red', 'status-dot--green', 'status-dot--orange', 'status-dot--blue');
        if (device.is_new_update_24h) {
          statusDot.classList.add('status-dot--blue');
        } else if (!device.detected_version) {
          statusDot.classList.add('status-dot--orange');
        } else {
          statusDot.classList.add(device.changed ? 'status-dot--red' : 'status-dot--green');
        }
      }

      const cat = existing.querySelector('.category');
      if (cat) cat.textContent = device.category || '';

      const storedSpan = existing.querySelector('.stored-version');
      if (storedSpan) storedSpan.textContent = device.stored_version || 'brak';

      const detectedSpan = existing.querySelector('.detected-version');
      if (detectedSpan) detectedSpan.textContent = device.detected_version || 'nieznana';

      const storedDate = existing.querySelector('.stored-date');
      if (storedDate) storedDate.textContent = device.stored_release_date || '-';
      const detectedDate = existing.querySelector('.detected-date');
      if (detectedDate) detectedDate.textContent = device.detected_release_date || '-';

      const ackBtn = existing.querySelector('.ack-btn');
      if (ackBtn) {
        ackBtn.disabled = !device.changed;
        ackBtn.onclick = async () => {
          ackBtn.disabled = true;
          try {
            const r = await fetch(API_ACK, {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify({
                model: device.model,
                version: device.detected_version
              })
            });
            if (!r.ok) throw new Error('ack failed');
            await refreshAndRender();
          } catch (e) {
            console.error(e);
            alert('Zatwierdzanie nie powiodło się');
          } finally {
            ackBtn.disabled = false;
          }
        };
      }

      // update per-card classes
      try {
        const cardEl = existing.querySelector('.card');
        if (cardEl) {
          cardEl.classList.remove('card--outdated', 'card--unknown', 'card--loading', 'card--new-update');
          if (device.is_new_update_24h) {
            cardEl.classList.add('card--new-update');
          } else if (!device.detected_version) {
            cardEl.classList.add('card--unknown');
          } else if (device.changed) {
            cardEl.classList.add('card--outdated');
          }
        }
      } catch (e) {
        console.warn('renderDevices: updating card classes failed', e);
      }

      // update or remove badge-new-update
      try {
        let badgeEl = existing.querySelector('.badge-new-update');
        if (device.is_new_update_24h) {
          if (!badgeEl) {
            badgeEl = document.createElement('div');
            badgeEl.className = 'badge-new-update';
            badgeEl.innerText = 'Nowa wersja (<24h)';
            const detectedContainer = existing.querySelector('.version-info:last-of-type') || existing.querySelector('.card-body');
            if (detectedContainer) detectedContainer.appendChild(badgeEl);
          }
        } else if (badgeEl) {
          badgeEl.remove();
        }
      } catch (e) {
        console.warn('renderDevices: badge update failed', e);
      }

      // update or remove update_info
      try {
        const updateInfoEl = existing.querySelector('.update-info');
        if (device.update_info) {
          if (updateInfoEl) updateInfoEl.innerHTML = device.update_info;
          else {
            const el = document.createElement('div');
            el.className = 'alert alert-warning mt-2 mb-0 py-1 px-2 small update-info';
            el.innerHTML = device.update_info;
            const detectedContainer = existing.querySelector('.version-info:last-of-type') || existing.querySelector('.card-body');
            if (detectedContainer) detectedContainer.appendChild(el);
          }
        } else if (updateInfoEl) {
          try { updateInfoEl.remove(); } catch (remErr) { console.warn('could not remove updateInfoEl', remErr); }
        }
      } catch (err) {
        console.warn('renderDevices: update_info DOM operation failed', err);
      }
    } else {
      container.appendChild(makeCard(device));
    }
  });

  // remove any DOM cards not present in devices
  Array.from(container.querySelectorAll('[data-model]')).forEach(el => {
    try {
      const m = el.getAttribute('data-model');
      if (!seen.has(m)) {
        if (el.parentNode) el.parentNode.removeChild(el);
      }
    } catch (err) {
      console.warn('renderDevices: failed to remove element for model', el, err);
    }
  });
}

// Update the small last-update text (hh:mm) and sync dot
function updateStatusBar(devices) {
  try {
    const el = document.getElementById('last-update');
    if (!el) return;
    const now = new Date();
    const time = now.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    const hasChanged = Array.isArray(devices) ? devices.some(d => d.changed) : false;
    const hasUnknown = Array.isArray(devices) ? devices.some(d => !d.detected_version) : false;
    let cls = 'sync-green';
    if (hasChanged) cls = 'sync-red';
    else if (window.__isRefreshing || hasUnknown) cls = 'sync-orange';
    el.innerHTML = `ostatnie sprawdzanie: ${time} <span class="sync-dot ${cls}"></span>`;
  } catch (err) {
    console.warn('updateStatusBar failed', err);
  }
}

async function refreshAndRender() {
  if (window.__isRefreshing) {
    console.log('[refreshAndRender] already running, skipping');
    return;
  }
  window.__isRefreshing = true;
  showLoader();
  try {
    await fetch(API_REFRESH, {method: 'POST'});
    const data = await fetchStatus();
    const devices = data.devices || [];
    window.__lastDevices = devices;
    console.log('[refreshAndRender] fetched devices count:', devices.length);
    if (!Array.isArray(devices) || devices.length === 0) {
      console.warn('[refreshAndRender] no devices returned; keeping current DOM');
      return;
    }
    renderDevices(devices);
    updateStatusBar(devices);
  } catch (e) {
    console.error(e);
    try {
      const data = await fetchStatus();
      const devices = data.devices || [];
      if (Array.isArray(devices) && devices.length > 0) {
        renderDevices(devices);
        updateStatusBar(devices);
      }
    } catch (err) {
      console.warn('[refreshAndRender] fallback failed, leaving DOM as-is', err);
    }
  } finally {
    hideLoader();
    window.__isRefreshing = false;
  }
}

// --- Polling support (safe, non-blocking) ---
let pollMs = 60000; // 60 seconds
let pollHandle = null;

async function pollOnce() {
  if (window.__isRefreshing) return;
  try {
    const data = await fetchStatus();
    const devices = data.devices || [];
    if (Array.isArray(devices) && devices.length > 0) {
      renderDevices(devices);
      updateStatusBar(devices);
    }
  } catch (err) {
    console.warn('[pollOnce] fetch failed', err);
  }
}

function startPolling() {
  if (pollHandle) return;
  pollHandle = setInterval(pollOnce, pollMs);
  console.log('[poll] started, interval ms=', pollMs);
}

function stopPolling() {
  if (!pollHandle) return;
  clearInterval(pollHandle);
  pollHandle = null;
  console.log('[poll] stopped');
}

// Pause polling when the tab is hidden
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopPolling();
  } else {
    startPolling();
    pollOnce();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const refreshBtn = document.getElementById('refreshBtn');

  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      try {
        await refreshAndRender();
      } catch (e) {
        console.error(e);
        alert('Odświeżanie nie powiodło się');
      } finally {
        refreshBtn.disabled = false;
      }
    });
  }

  // initial load
  (async () => {
    try {
      const data = await fetchStatus();
      const devices = data.devices || [];
      renderDevices(devices);
      updateStatusBar(devices);
    } catch (e) {
      const container = document.getElementById('cards');
      if (container) container.innerHTML = `<div class="alert alert-danger">Błąd ładowania danych: ${e.message}</div>`;
    }
  })();

  startPolling();
});

window.addEventListener('error', function (ev) {
  try {
    console.error('[global error]', ev.message, 'file:', ev.filename, 'line:', ev.lineno, 'col:', ev.colno, ev.error);
  } catch (e) {
    console.error('error logging failed', e);
  }
});

window.addEventListener('unhandledrejection', function (ev) {
  console.error('[unhandledrejection]', ev.reason);
});
