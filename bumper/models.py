from django.db import models
from django.utils import timezone

class Listing(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('sold', 'Sold'),
        ('unknown', 'Unknown'),
    ]

    thread_id = models.CharField(max_length=100, unique=True)
    title = models.TextField()
    url = models.URLField(max_length=1000)
    category = models.CharField(max_length=255, blank=True, default='')
    price = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    last_bumped = models.DateTimeField(null=True, blank=True)
    next_bump_due = models.DateTimeField(null=True, blank=True)
    bump_count = models.PositiveIntegerField(default=0)
    bump_enabled = models.BooleanField(default=True)
    bump_interval_seconds = models.PositiveIntegerField(default=1800)  # Specific interval (default 30 mins)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    @property
    def bumps_last_24h(self):
        """
        Returns the number of successful bumps in the last 24 hours.
        """
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=24)
        return self.bump_logs.filter(success=True, timestamp__gte=cutoff).count()

    @property
    def bump_due(self):
        if not self.bump_enabled or self.status != 'active':
            return False
        if self.bumps_last_24h >= 4:
            return False
        if self.next_bump_due is None:
            return True
        return timezone.now() >= self.next_bump_due

    @property
    def time_since_bump(self):
        if not self.last_bumped:
            return "Never bumped"
        
        now = timezone.now()
        diff = now - self.last_bumped
        seconds = diff.total_seconds()
        
        if seconds < 0:
            return "just now"
        if seconds < 60:
            return "just now"
        
        minutes = int(seconds // 60)
        if minutes < 60:
            return f"{minutes}m ago"
        
        hours = int(minutes // 60)
        if hours < 24:
            return f"{hours}h ago"
        
        days = int(hours // 24)
        return f"{days}d ago"

    @property
    def interval_value_and_unit(self):
        """
        Deconstructs interval seconds into numeric value and human unit text for HTML selectors.
        """
        seconds = self.bump_interval_seconds
        if seconds % 86400 == 0:
            return seconds // 86400, 'days'
        if seconds % 3600 == 0:
            return seconds // 3600, 'hours'
        if seconds % 60 == 0:
            return seconds // 60, 'minutes'
        return seconds, 'seconds'

    def __str__(self):
        return f"{self.title} (ID: {self.thread_id})"

    class Meta:
        ordering = ['-last_seen']


class BumpLog(models.Model):
    TRIGGER_CHOICES = [
        ('auto', 'Auto'),
        ('manual', 'Manual'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bump_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()
    message = models.TextField(blank=True, default='')
    triggered_by = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='auto')

    def __str__(self):
        status_str = "Success" if self.success else "Failed"
        return f"Bump {self.listing.thread_id} - {status_str} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']


class ScrapeLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()
    listings_found = models.PositiveIntegerField(default=0)
    listings_new = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True, default='')

    def __str__(self):
        status_str = "Success" if self.success else "Failed"
        return f"Scrape {status_str} at {self.timestamp} (Found: {self.listings_found}, New: {self.listings_new})"

    class Meta:
        ordering = ['-timestamp']
