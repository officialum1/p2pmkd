import re
import time
import random
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Listing, BumpLog, ScrapeLog

def get_playerup_session():
    """
    Builds a requests.Session with realistic headers and the xf_session cookie.
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.playerup.com/',
        'Origin': 'https://www.playerup.com',
    })
    cookie_val = getattr(settings, 'PLAYERUP_SESSION_COOKIE', '')
    if cookie_val:
        session.cookies.set('xf_session', cookie_val, domain='www.playerup.com')
    return session

def scrape_my_listings() -> dict:
    """
    Scrapes user's threads from PlayerUp recent content pages.
    """
    username = getattr(settings, 'PLAYERUP_USERNAME', '')
    if not username:
        err_msg = "PLAYERUP_USERNAME is not configured in settings."
        ScrapeLog.objects.create(success=False, message=err_msg)
        return {'found': 0, 'new': 0, 'error': err_msg}

    session = get_playerup_session()
    base_url = f"https://www.playerup.com/members/{username}/recent-content/"
    
    page = 1
    total_found = 0
    total_new = 0
    scraped_threads = set()
    
    try:
        while True:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            response = session.get(url, timeout=20)
            
            if response.status_code != 200:
                err_msg = f"Failed to retrieve page {page}. Status code: {response.status_code}"
                ScrapeLog.objects.create(success=False, message=err_msg)
                return {'found': total_found, 'new': total_new, 'error': err_msg}
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find listing elements with different selectors in order
            items = soup.select('li.discussionListItem')
            if not items:
                items = soup.select('.searchResult')
            if not items:
                items = soup.select('.block-row')
            
            if not items:
                # No more listings found on this page
                break
                
            page_found_count = 0
            
            for item in items:
                # Resolve link and title
                link_el = None
                if item.name == 'li' and 'discussionListItem' in item.get('class', []):
                    link_el = item.select_one('a.PreviewTooltip') or item.select_one('.title a')
                else:
                    link_el = item.select_one('h3 a') or item.select_one('.contentRow-title a') or item.select_one('a')
                
                if not link_el:
                    continue
                
                title = link_el.text.strip()
                href = link_el.get('href', '')
                if not href:
                    continue
                
                # Form absolute URL
                if not href.startswith('http'):
                    full_url = 'https://www.playerup.com/' + href.lstrip('/')
                else:
                    full_url = href
                
                # Extract thread_id
                # Pattern 1: /threads/[^/]+\.(\d+)/
                # Pattern 2: /threads/(\d+)/
                match = re.search(r'/threads/[^/]+\.(\d+)/', full_url)
                if not match:
                    match = re.search(r'/threads/(\d+)/', full_url)
                
                if not match:
                    continue
                
                thread_id = match.group(1)
                
                # Prevent duplicate processing on the same scrape run
                if thread_id in scraped_threads:
                    continue
                scraped_threads.add(thread_id)
                page_found_count += 1
                total_found += 1
                
                # Extract category if possible
                category = ""
                for a_tag in item.find_all('a'):
                    href_val = a_tag.get('href', '')
                    if '/forums/' in href_val:
                        category = a_tag.text.strip()
                        break
                
                # Extract price from title
                price_match = re.search(r'\$\d+(?:\.\d+)?|\d+\s*\$', title)
                price = price_match.group(0) if price_match else ''
                
                # Create or Update listing
                listing, created = Listing.objects.get_or_create(
                    thread_id=thread_id,
                    defaults={
                        'title': title,
                        'url': full_url,
                        'category': category,
                        'price': price,
                        'status': 'active',
                        'next_bump_due': timezone.now(),
                    }
                )
                
                if created:
                    total_new += 1
                else:
                    listing.title = title
                    listing.url = full_url
                    if category:
                        listing.category = category
                    if price:
                        listing.price = price
                    listing.status = 'active'  # keep it active on scrapes
                    listing.save()
            
            if page_found_count == 0:
                # No valid listings parsed on this page
                break
            
            # Check for next page pagination link
            next_link = soup.find('a', rel='next')
            if not next_link:
                # Try finding class with "next" in it
                next_link = soup.find('a', class_=lambda c: c and 'next' in c.lower())
            if not next_link:
                # Try text containing "Next"
                next_link = soup.find(lambda tag: tag.name == 'a' and 'next' in tag.text.lower())
                
            if not next_link:
                # No next page nav element
                break
                
            page += 1
            time.sleep(random.uniform(1.5, 3.0)) # Polite scraping delay
            
        success_msg = f"Scraped successfully. Total found: {total_found}, New: {total_new}."
        ScrapeLog.objects.create(
            success=True, 
            listings_found=total_found, 
            listings_new=total_new, 
            message=success_msg
        )
        return {'found': total_found, 'new': total_new, 'error': None}
        
    except Exception as e:
        err_msg = f"Scraping error encountered: {str(e)}"
        ScrapeLog.objects.create(success=False, message=err_msg)
        return {'found': total_found, 'new': total_new, 'error': err_msg}

def bump_listing(listing, triggered_by='auto') -> dict:
    """
    Simulates user action to bump a specific thread on PlayerUp.
    """
    session = get_playerup_session()
    
    try:
        # Step 2: Fetch listing thread page
        response = session.get(listing.url, timeout=20)
        if response.status_code != 200:
            err_msg = f"Failed to retrieve listing page. Status: {response.status_code}"
            BumpLog.objects.create(listing=listing, success=False, message=err_msg, triggered_by=triggered_by)
            return {'success': False, 'message': err_msg, 'rate_limited': False}
        
        # Step 3: Check for rate-limiting patterns BEFORE clicking
        rate_limit_phrases = ["you must wait", "too soon", "already bumped", "limit reached", "flood check"]
        page_html_lower = response.text.lower()
        is_rate_limited = any(phrase in page_html_lower for phrase in rate_limit_phrases)
        
        if is_rate_limited:
            msg = "Rate limit detected on listing page before bump attempt."
            BumpLog.objects.create(listing=listing, success=False, message=msg, triggered_by=triggered_by)
            return {'success': False, 'message': msg, 'rate_limited': True}
        
        # Step 4: Parse HTML to find the bump form or link
        soup = BeautifulSoup(response.text, 'lxml')
        
        bump_form = None
        form_data = {}
        action_url = None
        
        # Pattern A: Form submission
        for form in soup.find_all('form'):
            submit_btn = form.find('input', type='submit', value=re.compile(r'^bump$', re.I))
            if not submit_btn:
                submit_btn = form.find('button', type='submit', string=re.compile(r'bump', re.I))
            
            if submit_btn:
                bump_form = form
                action_url = form.get('action', '')
                for input_el in form.find_all(['input', 'select', 'textarea']):
                    name = input_el.get('name')
                    if name:
                        value = input_el.get('value', '')
                        if input_el.name == 'input' and input_el.get('type') in ['checkbox', 'radio']:
                            if not input_el.has_attr('checked'):
                                continue
                        form_data[name] = value
                break
        
        # Pattern B: Link GET
        bump_link_url = None
        if not bump_form:
            link = soup.find('a', href=re.compile(r'/up$'))
            if not link:
                link = soup.select_one('a.UpControl')
            if not link:
                link = soup.find('a', string=re.compile(r'^bump$', re.I))
                
            if link:
                bump_link_url = link.get('href', '')
        
        # Wait a random time before submitting (polite/anti-bot behavior)
        time.sleep(random.uniform(0.8, 2.0))
        
        post_response = None
        if bump_form:
            if action_url and not action_url.startswith('http'):
                action_url = 'https://www.playerup.com/' + action_url.lstrip('/')
            elif not action_url:
                action_url = listing.url
                
            post_response = session.post(action_url, data=form_data, timeout=20)
            
        elif bump_link_url:
            if not bump_link_url.startswith('http'):
                bump_link_url = 'https://www.playerup.com/' + bump_link_url.lstrip('/')
            post_response = session.get(bump_link_url, timeout=20)
            
        else:
            msg = "Bump control element (form submit or link) not found on page."
            BumpLog.objects.create(listing=listing, success=False, message=msg, triggered_by=triggered_by)
            return {'success': False, 'message': msg, 'rate_limited': False}
            
        if post_response.status_code != 200:
            err_msg = f"Bumping request failed with status: {post_response.status_code}"
            BumpLog.objects.create(listing=listing, success=False, message=err_msg, triggered_by=triggered_by)
            return {'success': False, 'message': err_msg, 'rate_limited': False}
            
        # Step 6 & 7: Check response for success and rate-limit triggers
        success_phrases = ["thread has been bumped", "thread bumped", "bumped successfully"]
        response_text_lower = post_response.text.lower()
        
        bump_success = any(phrase in response_text_lower for phrase in success_phrases)
        bump_rate_limited = any(phrase in response_text_lower for phrase in rate_limit_phrases)
        
        if bump_success:
            listing.last_bumped = timezone.now()
            listing.next_bump_due = timezone.now() + timedelta(seconds=listing.bump_interval_seconds)
            listing.bump_count += 1
            listing.save()
            
            msg = "Thread bumped successfully."
            BumpLog.objects.create(listing=listing, success=True, message=msg, triggered_by=triggered_by)
            return {'success': True, 'message': msg, 'rate_limited': False}
            
        elif bump_rate_limited:
            msg = "Rate limit detected during bump submission."
            BumpLog.objects.create(listing=listing, success=False, message=msg, triggered_by=triggered_by)
            return {'success': False, 'message': msg, 'rate_limited': True}
            
        else:
            # Sometimes XenForo doesn't give a clear confirmation page but redirects or works.
            # However, if it didn't give rate limit, we can treat it as failed bump for safety.
            snippet = post_response.text[:200].replace('\n', ' ')
            msg = f"Bump response did not contain success confirmation. Snippet: {snippet}"
            BumpLog.objects.create(listing=listing, success=False, message=msg, triggered_by=triggered_by)
            return {'success': False, 'message': msg, 'rate_limited': False}
            
    except Exception as e:
        err_msg = f"Network or execution error: {str(e)}"
        BumpLog.objects.create(listing=listing, success=False, message=err_msg, triggered_by=triggered_by)
        return {'success': False, 'message': err_msg, 'rate_limited': False}
