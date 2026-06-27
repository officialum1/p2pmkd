from django.urls import path
from . import views

app_name = 'bumper'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('logs/', views.logs, name='logs'),
    path('bump/<int:id>/', views.bump_now, name='bump_now'),
    path('toggle/<int:id>/', views.toggle_listing, name='toggle_listing'),
    path('scrape/', views.scrape_now, name='scrape_now'),
    path('api/sync-listings/', views.sync_listings, name='sync_listings'),
    path('api/log-bump/', views.log_bump, name='log_bump'),
    path('api/update-interval/<int:id>/', views.update_interval, name='update_interval'),
    path('api/update-interval-bulk/', views.update_interval_bulk, name='update_interval_bulk'),
    path('api/toggle-auto-bumper/', views.toggle_auto_bumper, name='toggle_auto_bumper'),
    path('api/analytics-data/', views.analytics_data, name='analytics_data'),
    path('live-status/', views.live_status, name='live_status'),
    path('analytics/', views.analytics, name='analytics'),
]
