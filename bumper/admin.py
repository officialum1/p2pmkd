from django.contrib import admin
from .models import Listing, BumpLog, ScrapeLog

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        'thread_id', 
        'title', 
        'category', 
        'price', 
        'status', 
        'bump_enabled', 
        'bump_count', 
        'last_bumped', 
        'next_bump_due'
    )
    list_filter = ('status', 'bump_enabled')
    search_fields = ('thread_id', 'title', 'category')
    readonly_fields = ('first_seen', 'last_seen')


@admin.register(BumpLog)
class BumpLogAdmin(admin.ModelAdmin):
    list_display = ('listing', 'success', 'triggered_by', 'timestamp', 'message')
    list_filter = ('success', 'triggered_by', 'timestamp')
    search_fields = ('listing__thread_id', 'listing__title', 'message')


@admin.register(ScrapeLog)
class ScrapeLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'success', 'listings_found', 'listings_new', 'message')
    list_filter = ('success', 'timestamp')
    search_fields = ('message',)
