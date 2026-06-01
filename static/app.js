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
  col.className = 'col-12'; // Changed from col-sm-6 col-md-4 - CSS Grid handles layout now
  col.setAttribute('data-model', device.model);

  const card = document.createElement('div');
  card.className = 'card h-100';

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
  // attach header to card
  card.appendChild(header);

  const statusDot = document.createElement('span');
  statusDot.className = 'status-dot';
  // status coloring: red when outdated (changed), orange when unknown, green when up-to-date
  if (!device.detected_version) {
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
  stored.innerHTML = `<strong>Stored:</strong> ${
    device.stored_version
      ? `<span class="version-value stored-version">${device.stored_version}</span>`
      : '<span class="version-none stored-version">none</span>'
  }`;

  const detected = document.createElement('div');
  detected.className = 'version-info';
  detected.innerHTML = `<strong>Detected:</strong> ${
    device.detected_version
      ? `<span class="version-value detected-version">${device.detected_version}</span>`
      : '<span class="version-none detected-version">unknown</span>'
  }`;

  if (device.update_info) {
    const updateInfo = document.createElement('div');
    updateInfo.className = 'alert alert-warning mt-2 mb-0 py-1 px-2 small update-info';
    updateInfo.innerHTML = device.update_info;
    detected.appendChild(updateInfo);
  }

  const dates = document.createElement('div');
  dates.className = 'text-muted small mt-2';
  dates.innerHTML = `<strong>Stored date:</strong> <span class="stored-date">${device.stored_release_date || '-'}</span><br><strong>Detected date:</strong> <span class="detected-date">${device.detected_release_date || '-'}</span>`;

  const btnGroup = document.createElement('div');
  btnGroup.className = 'mt-3 d-flex gap-2';

  const ackBtn = document.createElement('button');
  ackBtn.className = 'btn btn-sm btn-outline-success ack-btn';
  ackBtn.innerText = 'Acknowledge';
  ackBtn.disabled = !device.changed;
  ackBtn.onclick = async () => {
    ackBtn.disabled = true;
    try {
      const r = await fetch(API_ACK, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({model: device.model})});
      if (!r.ok) throw new Error('ack failed');
      await refreshAndRender();
    } catch (e) {
      console.error(e);
      alert('Acknowledgement failed');
    } finally {
      ackBtn.disabled = false;
    }
  };

  const storeBtn = document.createElement('button');
  storeBtn.className = 'btn btn-store btn-sm store-btn';
  storeBtn.innerText = 'Store Version';
  storeBtn.onclick = async () => {
    storeBtn.disabled = true;
    try {
      const r = await fetch('/api/store_version', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          model: device.model,
          version: device.detected_version,
          date: new Date().toISOString()
        })
      });
      if (!r.ok) throw new Error('store failed');
      await refreshAndRender();
    } catch (e) {
      console.error(e);
      alert('Storing version failed');
    } finally {
      storeBtn.disabled = false;
    }
  };

  // body content (title already in header)
  body.appendChild(category);
  versionsContainer.appendChild(stored);
  versionsContainer.appendChild(detected);
  body.appendChild(versionsContainer);
  body.appendChild(dates);

  // buttons group
  btnGroup.appendChild(ackBtn);
  btnGroup.appendChild(storeBtn);
  body.appendChild(btnGroup);

  card.appendChild(body);
  // apply per-card visual classes for known statuses
  if (!device.detected_version) {
    card.classList.add('card--unknown');
  } else if (device.changed) {
    card.classList.add('card--outdated');
  }

  col.appendChild(card);
  return col;
}

// Simple loader overlay control (creates overlay element once)
function showLoader() {
  let overlay = document.getElementById('loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.innerHTML = `<div class="loader-inner"><div class="spinner"></div><div class="loader-text">Loading…</div></div>`;
    document.body.appendChild(overlay);
  }
  overlay.classList.add('visible');
  // mark all cards as loading (visual orange) while loader is visible
  try {
    const cards = document.querySelectorAll('#cards .card');
    const dots = document.querySelectorAll('#cards .status-dot');
    cards.forEach(c => c.classList.add('card--loading'));
    dots.forEach(d => {
      d.classList.remove('status-dot--red', 'status-dot--green', 'status-dot--orange');
      d.classList.add('status-dot--orange');
    });
  } catch (e) {
    console.warn('showLoader: could not add loading class to cards', e);
  }
}

function hideLoader() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('visible');
  // remove loading state from cards and restore original status dots
  try {
    const cards = document.querySelectorAll('#cards .card');
    const dots = document.querySelectorAll('#cards .status-dot');
    cards.forEach(c => c.classList.remove('card--loading'));
    // After removing loading, re-render to restore correct status colors
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
    // find by data-model attribute
    const selector = `[data-model="${device.model}"]`;
    const existing = container.querySelector(selector);
    if (existing) {
      // update fields
      const title = existing.querySelector('.card-title');
      if (title) title.textContent = device.model;

      const statusDot = existing.querySelector('.status-dot');
      if (statusDot) {
        statusDot.classList.remove('status-dot--red', 'status-dot--green', 'status-dot--orange');
        if (!device.detected_version) {
          statusDot.classList.add('status-dot--orange');
        } else {
          statusDot.classList.add(device.changed ? 'status-dot--red' : 'status-dot--green');
        }
      }

      const cat = existing.querySelector('.category');
      if (cat) cat.textContent = device.category || '';

      const storedSpan = existing.querySelector('.stored-version');
      if (storedSpan) storedSpan.textContent = device.stored_version || 'none';

      const detectedSpan = existing.querySelector('.detected-version');
      if (detectedSpan) detectedSpan.textContent = device.detected_version || 'unknown';

      const storedDate = existing.querySelector('.stored-date');
      if (storedDate) storedDate.textContent = device.stored_release_date || '-';
      const detectedDate = existing.querySelector('.detected-date');
      if (detectedDate) detectedDate.textContent = device.detected_release_date || '-';

      const ackBtn = existing.querySelector('.ack-btn');
      if (ackBtn) ackBtn.disabled = !device.changed;

      // update per-card classes
      try {
        const cardEl = existing.querySelector('.card');
        if (cardEl) {
          cardEl.classList.remove('card--outdated', 'card--unknown', 'card--loading');
          if (!device.detected_version) cardEl.classList.add('card--unknown');
          else if (device.changed) cardEl.classList.add('card--outdated');
        }
      } catch (e) {
        console.warn('renderDevices: updating card classes failed', e);
      }

      // update or remove update_info (defensive - DOM may change concurrently)
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
      // create new card
      container.appendChild(makeCard(device));
    }
  });

  // remove any DOM cards not present in devices (defensive removal)
  Array.from(container.querySelectorAll('[data-model]')).forEach(el => {
    try {
      const m = el.getAttribute('data-model');
      if (!seen.has(m)) {
        if (el.parentNode) el.parentNode.removeChild(el);
      }
    } catch (err) {
      console.warn('renderDevices: failed to remove element for model', el && el.getAttribute ? el.getAttribute('data-model') : el, err);
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
    // overall status logic (priority: red > orange > green)
    const hasChanged = Array.isArray(devices) ? devices.some(d => d.changed) : false;
    const hasUnknown = Array.isArray(devices) ? devices.some(d => !d.detected_version) : false;
    // if any changed -> red; else if any unknown or currently refreshing -> orange; else green
    let cls = 'sync-green';
    if (hasChanged) cls = 'sync-red';
    else if (window.__isRefreshing || hasUnknown) cls = 'sync-orange';
    el.innerHTML = `Last update: ${time} <span class="sync-dot ${cls}"></span>`;
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
    // call refresh endpoint to trigger backend update
    await fetch(API_REFRESH, {method: 'POST'});
    const data = await fetchStatus();
    const devices = data.devices || [];
    window.__lastDevices = devices;  // store for restoring after loading
    console.log('[refreshAndRender] fetched devices count:', devices.length);
    if (!Array.isArray(devices) || devices.length === 0) {
      console.warn('[refreshAndRender] no devices returned; keeping current DOM');
      return;
    }
    renderDevices(devices);
    updateStatusBar(devices);
  } catch (e) {
    console.error(e);
    // on error, keep current DOM intact and log; try a best-effort status fetch without clobbering
    try {
      const data = await fetchStatus();
      const devices = data.devices || [];
      if (Array.isArray(devices) && devices.length > 0) {
        console.log('[refreshAndRender] fallback fetched devices count:', devices.length);
        renderDevices(devices);
        updateStatusBar(devices);
      } else {
        console.warn('[refreshAndRender] fallback returned no devices; leaving DOM as-is');
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
  if (window.__isRefreshing) return; // avoid overlap with manual refresh
  try {
    const data = await fetchStatus();
    const devices = data.devices || [];
    if (Array.isArray(devices) && devices.length > 0) {
      // render silently (no loader)
      renderDevices(devices);
      console.log('[pollOnce] updated devices count:', devices.length);
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

// Pause polling when the tab is hidden to save resources
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopPolling();
  } else {
    // resume and fetch immediately
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
        alert('Refresh failed');
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
      if (container) container.innerHTML = `<div class="alert alert-danger">Error loading data: ${e.message}</div>`;
    }
  })();
  // start background polling
  startPolling();
});

// Global error handlers to capture DOM exceptions and unhandled promise rejections
window.addEventListener('error', function (ev) {
  try {
    console.error('[global error]', ev.message, 'file:', ev.filename, 'line:', ev.lineno, 'col:', ev.colno, ev.error);
    console.log('[global error] current #cards count:', document.querySelectorAll('#cards [data-model]').length);
  } catch (e) {
    console.error('error logging failed', e);
  }
});

window.addEventListener('unhandledrejection', function (ev) {
  console.error('[unhandledrejection]', ev.reason);
});
