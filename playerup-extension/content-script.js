(function() {
  console.log('[PlayerUp Sync] Content script active on page.');

  // ==========================================
  // BROWSER-SIDE AUTOMATED SYNC-AND-CLOSE
  // ==========================================
  if (window.location.hash === '#sync-auto') {
    window.history.replaceState(null, null, ' ');
    
    console.log('[PlayerUp Sync] Automated dashboard sync initiated.');
    try {
      const scraped = scrapePageListings();
      const username = extractPlayerUpUsername();
      if (scraped.length > 0) {
        chrome.runtime.sendMessage({
          type: 'LISTINGS_SCRAPED',
          listings: scraped,
          username: username,
          timestamp: Date.now()
        }, (response) => {
          if (response && response.success) {
            showNotificationBanner(scraped.length);
            setTimeout(() => {
              window.close();
            }, 1500);
          } else {
            console.error('[PlayerUp Sync] Extension background failed to process sync.');
            setTimeout(() => window.close(), 1500);
          }
        });
      } else {
        console.warn('[PlayerUp Sync] No listings parsed on page.');
        setTimeout(() => window.close(), 1500);
      }
    } catch (err) {
      console.error('[PlayerUp Sync] Automated scraper crashed:', err);
      setTimeout(() => window.close(), 1500);
    }
    return;
  }

  // ==========================================
  // BROWSER-SIDE BUMPER CONTROLLER
  // ==========================================
  
  if (window.location.hash.startsWith('#bump-')) {
    const hashParts = window.location.hash.substring(1).split('-');
    sessionStorage.setItem('bump_active', 'true');
    sessionStorage.setItem('bump_triggered_by', hashParts[1] || 'manual');
    sessionStorage.setItem('bump_listing_id', hashParts[2] || '');
    
    window.history.replaceState(null, null, ' ');
  }

  if (sessionStorage.getItem('bump_active') === 'true') {
    const listingId = sessionStorage.getItem('bump_listing_id');
    const triggeredBy = sessionStorage.getItem('bump_triggered_by');
    
    console.log(`[PlayerUp Sync] Active bump session running in tab. Listing ID: ${listingId}, Triggered By: ${triggeredBy}`);
    
    const successPhrases = ["this thread has been bumped", "thread bumped", "bumped successfully"];
    const rateLimitPhrases = ["you must wait", "too soon", "already bumped", "limit reached", "flood check"];
    
    // Continuous dynamic polling check (captures full page reloads, redirects, AND background AJAX DOM updates)
    const successPoller = setInterval(() => {
      const pageText = document.body.textContent.toLowerCase();
      
      // 1. Check success criteria
      const isSuccess = successPhrases.some(phrase => pageText.includes(phrase));
      if (isSuccess) {
        clearInterval(successPoller);
        console.log('[PlayerUp Sync] Success banner detected via active polling! Logging results...');
        
        chrome.runtime.sendMessage({
          type: 'BUMP_RECORD',
          listingId: listingId,
          success: true,
          message: 'Thread bumped successfully in browser.',
          triggered_by: triggeredBy
        });
        
        sessionStorage.removeItem('bump_active');
        sessionStorage.removeItem('bump_listing_id');
        sessionStorage.removeItem('bump_triggered_by');
        
        setTimeout(() => {
          window.close();
        }, 1200);
        return;
      }
      
      // 2. Check rate limit criteria
      const isRateLimited = rateLimitPhrases.some(phrase => pageText.includes(phrase));
      if (isRateLimited) {
        clearInterval(successPoller);
        console.warn('[PlayerUp Sync] Rate limit detected via active polling.');
        
        chrome.runtime.sendMessage({
          type: 'BUMP_RECORD',
          listingId: listingId,
          success: false,
          message: 'Rate limit detected during bump submission.',
          triggered_by: triggeredBy
        });
        
        sessionStorage.removeItem('bump_active');
        sessionStorage.removeItem('bump_listing_id');
        sessionStorage.removeItem('bump_triggered_by');
        
        setTimeout(() => {
          window.close();
        }, 1200);
        return;
      }
    }, 500); // Poll every 500 milliseconds

    // D. Search and click the bump controls (if loaded on initial view)
    const bumpBtn = document.querySelector('a#upButtonCountdown, a.UpControl, a.UpButtonView') || 
                    document.querySelector('a[href$="/up"]') || 
                    Array.from(document.querySelectorAll('a')).find(a => a.href && a.href.includes('/up'));
                    
    if (bumpBtn) {
      console.log('[PlayerUp Sync] Found bump button. Simulating user click...');
      
      let targetHref = bumpBtn.getAttribute('href') || '';
      if (targetHref && !targetHref.startsWith('http')) {
        if (targetHref.startsWith('/')) {
          targetHref = 'https://www.playerup.com' + targetHref;
        } else {
          targetHref = 'https://www.playerup.com/' + targetHref.replace(/^\//, '');
        }
      } else {
        targetHref = bumpBtn.href;
      }

      const delay = 1000 + Math.random() * 1000;
      setTimeout(() => {
        bumpBtn.click();
        
        // Navigation fallback in case ajax is bypassed
        setTimeout(() => {
          if (sessionStorage.getItem('bump_active') === 'true') {
            window.location.href = targetHref;
          }
        }, 2000);
      }, delay);
      
    } else {
      // In case button is missing, wait 5 seconds for poller to catch any lazy-loaded banners, else fail
      setTimeout(() => {
        if (sessionStorage.getItem('bump_active') === 'true') {
          clearInterval(successPoller);
          console.error('[PlayerUp Sync] Bump control element not found and poller timed out.');
          
          chrome.runtime.sendMessage({
            type: 'BUMP_RECORD',
            listingId: listingId,
            success: false,
            message: 'Bump control button not found on thread page.',
            triggered_by: triggeredBy
          });
          
          sessionStorage.removeItem('bump_active');
          sessionStorage.removeItem('bump_listing_id');
          sessionStorage.removeItem('bump_triggered_by');
          
          window.close();
        }
      }, 5000);
    }
    return;
  }

  // ==========================================
  // LISTINGS SCRAPER/HARVESTER
  // ==========================================

  function scrapePageListings() {
    const validListings = [];
    const seenIds = new Set();

    const items = document.querySelectorAll(
      'li.discussionListItem, .structItem, .searchResult, .block-row, div[data-author], tr'
    );

    items.forEach(item => {
      let link = null;
      const anchors = item.querySelectorAll('a');
      for (let a of anchors) {
        const href = a.href;
        if (href && href.includes('playerup.com/threads/')) {
          link = a;
          break;
        }
      }

      if (!link) return;

      const title = link.textContent.strip ? link.textContent.strip() : link.textContent.trim();
      const url = link.href;

      let threadId = null;
      let match = url.match(/threads\/[^/]+\.(\d+)\//);
      if (!match) {
        match = url.match(/threads\/(\d+)\//);
      }
      if (match) {
        threadId = match[1];
      }

      if (!threadId || seenIds.has(threadId)) return;
      seenIds.add(threadId);

      let category = '';
      const breadcrumb = document.querySelector('.crust a span, .p-breadcrumbs a');
      if (breadcrumb) {
        category = breadcrumb.textContent.trim();
      } else {
        const nodeTitle = item.querySelector('.node-title, .structItem-parts a, .forumLink') || document.querySelector('.p-title h1');
        if (nodeTitle) {
          category = nodeTitle.textContent.trim();
        }
      }

      const priceMatch = title.match(/\$\d+(?:\.\d+)?|\d+\s*\$/);
      const price = priceMatch ? priceMatch[0] : '';

      validListings.push({
        thread_id: threadId,
        title: title,
        url: url,
        category: category,
        price: price
      });
    });

    return validListings;
  }

  function extractPlayerUpUsername() {
    const urlMatch = window.location.href.match(/playerup\.com\/members\/([^/?#]+)/i);
    if (urlMatch) {
      return decodeURIComponent(urlMatch[1]).replace(/\/$/, '');
    }

    const links = Array.from(document.querySelectorAll('a[href*="/members/"]'));
    for (const link of links) {
      const href = link.href || '';
      const match = href.match(/\/members\/([^/?#]+)/i);
      if (!match) continue;

      const username = decodeURIComponent(match[1]).replace(/\/$/, '');
      if (username && !username.toLowerCase().includes('online')) {
        return username;
      }
    }

    return '';
  }

  try {
    const scraped = scrapePageListings();
    const username = extractPlayerUpUsername();
    console.log(`[PlayerUp Sync] Extracted ${scraped.length} valid listings from page.`, scraped);

    if (scraped.length > 0) {
      chrome.runtime.sendMessage({
        type: 'LISTINGS_SCRAPED',
        listings: scraped,
        username: username,
        timestamp: Date.now()
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('[PlayerUp Sync] Send message failed:', chrome.runtime.lastError.message);
          return;
        }
        
        if (response && response.success) {
          showNotificationBanner(scraped.length);
        }
      });
    }
  } catch (err) {
    console.error('[PlayerUp Sync] Scraper execution failed:', err);
  }

  function showNotificationBanner(count) {
    const banner = document.createElement('div');
    banner.style.position = 'fixed';
    banner.style.top = '0';
    banner.style.left = '0';
    banner.style.right = '0';
    banner.style.backgroundColor = '#22c55e';
    banner.style.color = '#ffffff';
    banner.style.padding = '14px 20px';
    banner.style.textAlign = 'center';
    banner.style.fontWeight = 'bold';
    banner.style.fontSize = '14px';
    banner.style.zIndex = '999999';
    banner.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.2)';
    banner.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    banner.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
    banner.innerText = `Synced ${count} listings to your PlayerUp Auto-Bumper Dashboard.`;
    
    document.body.appendChild(banner);
    
    banner.style.transform = 'translateY(-100%)';
    setTimeout(() => {
      banner.style.transform = 'translateY(0)';
    }, 100);

    setTimeout(() => {
      banner.style.transform = 'translateY(-100%)';
      banner.style.opacity = '0';
      setTimeout(() => banner.remove(), 400);
    }, 5000);
  }
})();
