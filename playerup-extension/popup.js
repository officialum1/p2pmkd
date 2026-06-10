document.addEventListener('DOMContentLoaded', async () => {
  console.log('[PlayerUp Sync] Popup loaded.');
  
  // 1. Initial configuration load
  await loadSettingsAndStats();
  
  // 2. Poll storage stats every 5 seconds to keep the UI in sync
  setInterval(loadSettingsAndStats, 5000);

  // 3. Sync Now Button handler
  document.getElementById('syncNow').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.textContent = 'Syncing...';
    btn.disabled = true;
    
    try {
      // Direct user to PlayerUp recent content page where scraper is injected
      await chrome.tabs.create({
        url: 'https://www.playerup.com/account/recent-content',
        active: true
      });
      showToast('Opening PlayerUp recent content page...');
    } catch (err) {
      console.error('[PlayerUp Sync] Failed to open tab:', err);
      showToast('Error opening page.');
    }

    setTimeout(() => {
      btn.textContent = 'Sync Now';
      btn.disabled = false;
    }, 3000);
  });

  // 4. Open Dashboard Button handler
  document.getElementById('openDashboard').addEventListener('click', async () => {
    try {
      const storage = await chrome.storage.local.get(['backendUrl']);
      const targetUrl = storage.backendUrl || CONFIG.BACKEND_URL;
      
      // Validate and ensure valid URL format
      let finalUrl = targetUrl;
      if (!finalUrl.startsWith('http://') && !finalUrl.startsWith('https://')) {
        finalUrl = 'http://' + finalUrl;
      }
      
      await chrome.tabs.create({ url: finalUrl });
    } catch (err) {
      console.error('[PlayerUp Sync] Open dashboard error:', err);
      showToast('Error opening dashboard.');
    }
  });

  // 5. Save Settings Button handler
  document.getElementById('saveSettings').addEventListener('click', async () => {
    const inputUrl = document.getElementById('backendUrl').value.trim();
    if (!inputUrl) {
      showToast('Please enter a valid URL.');
      return;
    }
    
    try {
      await chrome.storage.local.set({ backendUrl: inputUrl });
      showToast('Settings saved successfully!');
      await loadSettingsAndStats();
    } catch (err) {
      console.error('[PlayerUp Sync] Save settings error:', err);
      showToast('Failed to save settings.');
    }
  });
});

async function loadSettingsAndStats() {
  try {
    const storage = await chrome.storage.local.get([
      'backendUrl',
      'lastSync',
      'lastSyncCount',
      'lastSyncSuccess'
    ]);

    // Populate URL input
    const input = document.getElementById('backendUrl');
    const defaultUrl = storage.backendUrl || CONFIG.BACKEND_URL;
    if (input && !input.value) {
      input.value = defaultUrl;
    }

    // Populate Stats
    const lastSyncVal = storage.lastSync;
    const lastSyncCountVal = storage.lastSyncCount;
    
    document.getElementById('lastSync').textContent = formatTimeAgo(lastSyncVal);
    document.getElementById('listingCount').textContent = lastSyncCountVal !== undefined ? lastSyncCountVal : '0';

    // Populate Connection Status Indicators
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    if (!storage.backendUrl) {
      statusDot.className = 'status-indicator';
      statusText.textContent = 'Setup Required';
      statusText.style.color = 'var(--yellow)';
    } else if (storage.lastSyncSuccess === false) {
      statusDot.className = 'status-indicator error';
      statusText.textContent = 'Connection Error';
      statusText.style.color = 'var(--red)';
    } else {
      statusDot.className = 'status-indicator connected';
      statusText.textContent = 'Connected & Active';
      statusText.style.color = 'var(--green)';
    }

  } catch (err) {
    console.error('[PlayerUp Sync] Load settings error:', err);
  }
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return 'Never';
  
  const diff = Date.now() - timestamp;
  const seconds = Math.floor(diff / 1000);
  
  if (seconds < 60) return 'Just now';
  
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function showToast(message) {
  const toast = document.getElementById('popupToast');
  if (!toast) return;
  
  toast.textContent = message;
  toast.classList.remove('hidden');
  
  setTimeout(() => {
    toast.classList.add('hidden');
  }, 2500);
}
