importScripts('config.js');

console.log('[PlayerUp Sync] Service worker started.');

// Set up daily sync reminders
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('sync-reminder', {
    periodInMinutes: 1440 // 24 Hours
  });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'sync-reminder') {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'PlayerUp Sync Reminder',
      message: 'It has been 24 hours. Visit PlayerUp recent content page to sync your latest listings!'
    });
  }
});

// Message listener from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'LISTINGS_SCRAPED') {
    handleScrapedListings(message)
      .then(result => {
        sendResponse(result);
      })
      .catch(err => {
        console.error('[PlayerUp Sync] Error processing listings:', err);
        sendResponse({ success: false, error: err.message });
      });
    return true; // Keep message channel open for async response
  } else if (message.type === 'BUMP_RECORD') {
    handleBumpRecord(message)
      .then(result => {
        sendResponse(result);
      })
      .catch(err => {
        console.error('[PlayerUp Sync] Error logging bump:', err);
        sendResponse({ success: false, error: err.message });
      });
    return true; // Keep message channel open
  }
});

async function handleScrapedListings(message) {
  try {
    const cookies = await chrome.cookies.getAll({ domain: '.playerup.com' });
    const sessionCookie = cookies.find(c => c.name === 'xf_session');
    
    if (!sessionCookie) {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'PlayerUp Cookie Missing',
        message: 'Could not find xf_session cookie. Please log in to PlayerUp first!'
      });
      console.warn('[PlayerUp Sync] xf_session cookie not found.');
    }

    const storage = await chrome.storage.local.get(['backendUrl']);
    const backendUrl = storage.backendUrl || CONFIG.BACKEND_URL;

    const payload = {
      listings: message.listings,
      username: message.username || '',
      cookies: {
        xf_session: sessionCookie ? sessionCookie.value : ''
      },
      timestamp: Date.now()
    };

    let response = null;
    try {
      response = await sendSyncPayload(backendUrl, payload);
    } catch (err) {
      console.warn('[PlayerUp Sync] Sync failed. Retrying in 5 seconds...', err);
      await new Promise(resolve => setTimeout(resolve, 5000));
      response = await sendSyncPayload(backendUrl, payload);
    }

    if (response && response.success) {
      await chrome.storage.local.set({
        lastSync: Date.now(),
        lastSyncCount: message.listings.length,
        lastSyncSuccess: true,
        lastUsername: message.username || ''
      });

      chrome.action.setBadgeText({ text: String(message.listings.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#22c55e' });

      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'PlayerUp Sync Complete',
        message: `Successfully synced ${message.listings.length} listings to dashboard.`
      });

      return { success: true };
    } else {
      throw new Error(response ? response.message : 'Sync request rejected by backend.');
    }

  } catch (err) {
    console.error('[PlayerUp Sync] Sync operations failed:', err);
    await chrome.storage.local.set({ lastSyncSuccess: false });
    
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'PlayerUp Sync Failed',
      message: `Sync Error: ${err.message}`
    });
    
    return { success: false, error: err.message };
  }
}

async function sendSyncPayload(url, payload) {
  const cleanUrl = url.replace(/\/$/, '') + '/api/sync-listings/';
  const response = await fetch(cleanUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Server returned HTTP ${response.status}`);
  }

  return await response.json();
}

async function handleBumpRecord(message) {
  try {
    const storage = await chrome.storage.local.get(['backendUrl']);
    const backendUrl = storage.backendUrl || CONFIG.BACKEND_URL;
    const cleanUrl = backendUrl.replace(/\/$/, '') + '/api/log-bump/';

    const payload = {
      listing_id: message.listingId,
      success: message.success,
      message: message.message,
      triggered_by: message.triggered_by
    };

    console.log('[PlayerUp Sync] Logging browser bump outcome to backend:', payload);

    const response = await fetch(cleanUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const resData = await response.json();
    return resData;

  } catch (err) {
    console.error('[PlayerUp Sync] Failed to log bump to server:', err);
    return { success: false, error: err.message };
  }
}
