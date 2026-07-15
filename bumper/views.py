import json
import os
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.conf import settings
from .models import Listing, BumpLog, ScrapeLog, PlayerUpCredential, BumperSetting

@ensure_csrf_cookie
def dashboard(request):
    """
    Renders the Auto-Bumper dashboard with current listings, logs, and statistics.
    """
    listings = Listing.objects.all()
    total_listings = listings.count()
    
    active_listings_qs = listings.filter(status='active', bump_enabled=True)
    active_listings = active_listings_qs.count()
    
    due_now = sum(1 for l in active_listings_qs if l.bump_due)
    
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    bumps_today = BumpLog.objects.filter(success=True, timestamp__gte=today_start).count()
    
    recent_scrapes = ScrapeLog.objects.all()[:5]
    settings_obj = BumperSetting.current()
    
    context = {
        'listings': listings,
        'total_listings': total_listings,
        'active_listings': active_listings,
        'bumps_today': bumps_today,
        'due_now': due_now,
        'recent_scrapes': recent_scrapes,
        'browser_auto_bumper_enabled': settings_obj.browser_auto_bumper_enabled,
    }
    return render(request, 'bumper/dashboard.html', context)

def logs(request):
    """
    Renders audit logs for scrapes and bumps with custom criteria filters.
    """
    bump_logs = BumpLog.objects.select_related('listing').all()
    
    listing_id = request.GET.get('listing')
    if listing_id and listing_id.isdigit():
        bump_logs = bump_logs.filter(listing_id=int(listing_id))
        
    status_filter = request.GET.get('status')
    if status_filter == 'success':
        bump_logs = bump_logs.filter(success=True)
    elif status_filter == 'fail':
        bump_logs = bump_logs.filter(success=False)
        
    listings = Listing.objects.only('id', 'title', 'thread_id').all()
    
    context = {
        'bump_logs': bump_logs,
        'listings': listings,
        'selected_listing': listing_id,
        'selected_status': status_filter,
    }
    return render(request, 'bumper/logs.html', context)

@require_POST
def bump_now(request, id):
    """
    AJAX POST endpoint to manually trigger a bump for a single listing.
    """
    try:
        listing = get_object_or_404(Listing, id=id)
        result = bump_listing(listing, triggered_by='manual')
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f"Unexpected error: {str(e)}", 
            'rate_limited': False
        }, status=500)

@require_POST
def toggle_listing(request, id):
    """
    AJAX POST endpoint to toggle the auto-bumping flag of a single listing.
    """
    try:
        listing = get_object_or_404(Listing, id=id)
        listing.bump_enabled = not listing.bump_enabled
        listing.save()
        return JsonResponse({'bump_enabled': listing.bump_enabled})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
def scrape_now(request):
    """
    AJAX POST endpoint to trigger an immediate listings scrape.
    """
    try:
        result = scrape_my_listings()
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'found': 0, 
            'new': 0, 
            'error': f"Unexpected error: {str(e)}"
        }, status=500)

@csrf_exempt
@require_POST
def sync_listings(request):
    """
    POST API endpoint called by the Chrome extension.
    Accepts listings and optional PlayerUp session cookies to synchronize.
    """
    try:
        data = json.loads(request.body)
        listings_list = data.get('listings', [])
        cookies_data = data.get('cookies', {})
        username = (data.get('username') or data.get('playerup_username') or '').strip()
        
        cookie_val = None
        if isinstance(cookies_data, dict):
            cookie_val = cookies_data.get('xf_session')
        elif isinstance(cookies_data, list):
            for c in cookies_data:
                if c.get('name') == 'xf_session':
                    cookie_val = c.get('value')
                    break
        
        if cookie_val:
            setattr(settings, 'PLAYERUP_SESSION_COOKIE', cookie_val)

        if username:
            setattr(settings, 'PLAYERUP_USERNAME', username)

        if cookie_val or username:
            credential = PlayerUpCredential.current()
            if cookie_val:
                credential.xf_session = cookie_val
            if username:
                credential.username = username
            credential.save()

        if cookie_val or username:
            env_path = os.path.join(settings.BASE_DIR, '.env')
            if os.path.exists(env_path):
                try:
                    with open(env_path, 'r') as f:
                        lines = f.readlines()

                    cookie_found = False
                    username_found = False
                    for idx, line in enumerate(lines):
                        if line.strip().startswith('PLAYERUP_SESSION_COOKIE='):
                            if cookie_val:
                                lines[idx] = f'PLAYERUP_SESSION_COOKIE={cookie_val}\n'
                            cookie_found = True
                        elif line.strip().startswith('PLAYERUP_USERNAME='):
                            if username:
                                lines[idx] = f'PLAYERUP_USERNAME={username}\n'
                            username_found = True

                    if cookie_val and not cookie_found:
                        lines.append(f'PLAYERUP_SESSION_COOKIE={cookie_val}\n')
                    if username and not username_found:
                        lines.append(f'PLAYERUP_USERNAME={username}\n')
                    
                    with open(env_path, 'w') as f:
                        f.writelines(lines)
                except Exception:
                    pass

        # 2. Synchronize listing records
        synced_count = 0
        for l_data in listings_list:
            thread_id = l_data.get('thread_id')
            if not thread_id:
                continue
                
            title = l_data.get('title', 'Untitled Listing')
            url = l_data.get('url', '')
            category = l_data.get('category', '')
            price = l_data.get('price', '')
            
            listing, created = Listing.objects.update_or_create(
                thread_id=thread_id,
                defaults={
                    'title': title,
                    'url': url,
                    'category': category,
                    'price': price,
                    'status': 'active',
                }
            )
            if created:
                listing.next_bump_due = timezone.now()
                listing.save()
                
            synced_count += 1
            
        return JsonResponse({'success': True, 'synced': synced_count})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON request payload.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)

@csrf_exempt
@require_POST
def log_bump(request):
    """
    POST API endpoint called by the Chrome extension to record a browser-side bump attempt.
    """
    try:
        data = json.loads(request.body)
        listing_id = data.get('listing_id')
        success = data.get('success', False)
        message = data.get('message', '')
        triggered_by = data.get('triggered_by', 'auto')

        listing = get_object_or_404(Listing, id=listing_id)
        disable_listing = data.get('disable_listing', False)

        if success:
            listing.last_bumped = timezone.now()
            listing.next_bump_due = timezone.now() + timedelta(seconds=listing.bump_interval_seconds)
            listing.bump_count += 1
            listing.save()
        elif disable_listing:
            listing.bump_enabled = False
            listing.status = 'paused'
            listing.save()

        BumpLog.objects.create(
            listing=listing,
            success=success,
            message=message,
            triggered_by=triggered_by
        )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_POST
def update_interval(request, id):
    """
    POST API endpoint called by the dashboard to customize a thread's specific bump interval.
    """
    try:
        data = json.loads(request.body)
        value = int(data.get('value', 30))
        unit = data.get('unit', 'minutes')

        if value <= 0:
            return JsonResponse({'success': False, 'message': 'Interval value must be greater than zero.'}, status=400)

        listing = get_object_or_404(Listing, id=id)

        # Convert to seconds
        if unit == 'seconds':
            total_seconds = value
        elif unit == 'hours':
            total_seconds = value * 3600
        elif unit == 'days':
            total_seconds = value * 86400
        else:  # minutes
            total_seconds = value * 60

        listing.bump_interval_seconds = total_seconds

        # Recalculate next due time
        if listing.last_bumped:
            listing.next_bump_due = listing.last_bumped + timedelta(seconds=total_seconds)
        else:
            listing.next_bump_due = timezone.now() + timedelta(seconds=total_seconds)

        listing.save()

        local_time = timezone.localtime(listing.next_bump_due)
        return JsonResponse({
            'success': True, 
            'next_due': local_time.strftime('%H:%M:%S')
        })
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid numeric value.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_POST
def update_interval_bulk(request):
    """
    POST API endpoint called by the dashboard to customize specific listing schedules in bulk.
    """
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        value = int(data.get('value', 30))
        unit = data.get('unit', 'minutes')
        auto_state = data.get('auto_state', 'keep')

        if not ids:
            return JsonResponse({'success': False, 'message': 'No threads were selected.'}, status=400)

        if value <= 0:
            return JsonResponse({'success': False, 'message': 'Interval value must be greater than zero.'}, status=400)

        # Convert to seconds
        if unit == 'seconds':
            total_seconds = value
        elif unit == 'hours':
            total_seconds = value * 3600
        elif unit == 'days':
            total_seconds = value * 86400
        else:  # minutes
            total_seconds = value * 60

        listings = Listing.objects.filter(id__in=ids)
        updated_count = 0
        for listing in listings:
            listing.bump_interval_seconds = total_seconds
            
            if auto_state == 'enable':
                listing.bump_enabled = True
                listing.status = 'active'
            elif auto_state == 'disable':
                listing.bump_enabled = False
                listing.status = 'paused'

            # Recalculate next due time
            if listing.last_bumped:
                listing.next_bump_due = listing.last_bumped + timedelta(seconds=total_seconds)
            else:
                listing.next_bump_due = timezone.now() + timedelta(seconds=total_seconds)
            listing.save()
            updated_count += 1

        status_msg = ""
        if auto_state == 'enable':
            status_msg = " and activated"
        elif auto_state == 'disable':
            status_msg = " and paused"

        return JsonResponse({
            'success': True,
            'message': f'Successfully updated {updated_count} threads to {value} {unit}{status_msg}.'
        })
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid numeric value.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def live_status(request):
    """
    AJAX GET endpoint for client-side live polling and log stream updating.
    """
    try:
        active_listings_qs = Listing.objects.filter(status='active', bump_enabled=True)
        due_count = sum(1 for l in active_listings_qs if l.bump_due)
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        bumps_today = BumpLog.objects.filter(success=True, timestamp__gte=today_start).count()
        
        recent_logs = []
        logs_qs = BumpLog.objects.select_related('listing').all()[:10]
        
        for log in logs_qs:
            local_time = timezone.localtime(log.timestamp)
            recent_logs.append({
                'listing__title': log.listing.title,
                'success': log.success,
                'message': log.message,
                'triggered_by': log.triggered_by,
                'timestamp': local_time.strftime('%H:%M:%S')
            })
            
        due_listings = [{'id': l.id, 'url': l.url} for l in active_listings_qs if l.bump_due]
        settings_obj = BumperSetting.current()
            
        return JsonResponse({
            'due_count': due_count,
            'bumps_today': bumps_today,
            'recent_logs': recent_logs,
            'due_listings': due_listings,
            'browser_auto_bumper_enabled': settings_obj.browser_auto_bumper_enabled
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def toggle_auto_bumper(request):
    """
    POST API endpoint called by the dashboard to toggle global auto-bumper state.
    """
    try:
        data = json.loads(request.body)
        enabled = data.get('enabled', False)
        settings_obj = BumperSetting.current()
        settings_obj.browser_auto_bumper_enabled = enabled
        settings_obj.save()
        return JsonResponse({'success': True, 'enabled': settings_obj.browser_auto_bumper_enabled})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def analytics(request):
    """
    Renders the charts analytics page.
    """
    return render(request, 'bumper/analytics.html')

def analytics_data(request):
    """
    GET API endpoint to retrieve aggregated counts for Chart.js dashboard charts.
    """
    try:
        # 1. 7-Day Bumps Activity
        seven_days_ago = timezone.now() - timedelta(days=7)
        logs_last_7_days = BumpLog.objects.filter(timestamp__gte=seven_days_ago)
        
        daily_bumps = {}
        # Initialize last 7 days with 0
        for d in range(7):
            day = (timezone.now() - timedelta(days=d)).date()
            daily_bumps[day.strftime('%Y-%m-%d')] = 0
            
        for log in logs_last_7_days:
            if log.success:
                day_str = timezone.localtime(log.timestamp).date().strftime('%Y-%m-%d')
                if day_str in daily_bumps:
                    daily_bumps[day_str] += 1
                    
        # Sort keys chronologically
        sorted_days = sorted(daily_bumps.keys())
        daily_bumps_data = [daily_bumps[k] for k in sorted_days]
        
        # 2. Success vs Failure ratio
        success_count = BumpLog.objects.filter(success=True).count()
        failed_count = BumpLog.objects.filter(success=False).count()
        
        # 3. Top 5 listings
        top_listings = []
        for l in Listing.objects.all().order_by('-bump_count')[:5]:
            short_title = (l.title[:30] + '...') if len(l.title) > 30 else l.title
            top_listings.append({
                'title': short_title,
                'bump_count': l.bump_count
            })
            
        return JsonResponse({
            'daily_bumps_labels': sorted_days,
            'daily_bumps_data': daily_bumps_data,
            'ratio_labels': ['Success', 'Failed'],
            'ratio_data': [success_count, failed_count],
            'top_listings': top_listings
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def health_check(request):
    """
    Lightweight health check endpoint for Render to prevent timeout restarts.
    """
    return JsonResponse({'status': 'healthy'})
