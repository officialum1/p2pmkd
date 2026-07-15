import time
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

class Command(BaseCommand):
    help = 'Runs the automated PlayerUp scraper and thread bumper loop.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=getattr(settings, 'BUMP_INTERVAL_MINUTES', 30),
            help='Interval in minutes between listing bumps'
        )
        parser.add_argument(
            '--scrape-interval',
            type=int,
            default=60,
            help='Interval in minutes between user listing scrapes'
        )

    def handle(self, *args, **options):
        # Local imports to avoid Django app registry initialization errors
        from bumper.scraper import scrape_my_listings, bump_listing
        from bumper.models import Listing, ScrapeLog

        bump_interval_mins = options['interval']
        scrape_interval_mins = options['scrape_interval']

        self.stdout.write(self.style.SUCCESS(
            f"Bumper daemon started. "
            f"Bump Interval override: {bump_interval_mins}m, "
            f"Scrape Interval: {scrape_interval_mins}m"
        ))

        # Check last ScrapeLog time from DB
        last_scrape_qs = ScrapeLog.objects.filter(success=True).order_by('-timestamp')
        if last_scrape_qs.exists():
            last_scrape_time = last_scrape_qs.first().timestamp
            self.stdout.write(f"Last recorded successful scrape: {last_scrape_time}")
        else:
            last_scrape_time = None
            self.stdout.write("No prior successful scrapes found. Scrape will run on loop start.")

        try:
            while True:
                now = timezone.now()

                # 1. Evaluate if scraping is due
                should_scrape = False
                if last_scrape_time is None:
                    should_scrape = True
                else:
                    time_elapsed = now - last_scrape_time
                    if time_elapsed >= timedelta(minutes=scrape_interval_mins):
                        should_scrape = True

                if should_scrape:
                    self.stdout.write(self.style.WARNING("Initiating listings scrape..."))
                    result = scrape_my_listings()
                    last_scrape_time = timezone.now()
                    
                    if result.get('error'):
                        self.stdout.write(self.style.ERROR(f"Scraping failed: {result['error']}"))
                    else:
                        self.stdout.write(self.style.SUCCESS(
                            f"Scrape completed. Found: {result['found']}, New: {result['new']}"
                        ))

                # 2. Query and process due active threads
                active_listings = Listing.objects.filter(status='active', bump_enabled=True)
                due_listings = [l for l in active_listings if l.bump_due]

                if due_listings:
                    self.stdout.write(self.style.WARNING(f"Detected {len(due_listings)} due threads. Initiating bump sequence..."))
                    
                    for i, listing in enumerate(due_listings):
                        self.stdout.write(f"Bumping listing: {listing.thread_id} ({listing.title[:40]})")
                        
                        bump_result = bump_listing(listing, triggered_by='auto')
                        
                        if bump_result['success']:
                            self.stdout.write(self.style.SUCCESS(
                                f"Successfully bumped listing {listing.thread_id}."
                            ))
                        else:
                            if bump_result.get('rate_limited'):
                                self.stdout.write(self.style.WARNING(
                                    f"Rate limited. Terminating sequence loop to respect site limitations. "
                                    f"Message: {bump_result['message']}"
                                ))
                                break
                            else:
                                self.stdout.write(self.style.ERROR(
                                    f"Failed to bump listing {listing.thread_id}: {bump_result['message']}"
                                ))

                        # Delay between individual listing bumps to mimic human actions
                        if i < len(due_listings) - 1:
                            delay = random.uniform(5.0, 12.0)
                            self.stdout.write(f"Sleeping for {delay:.2f}s before processing next listing...")
                            time.sleep(delay)

                else:
                    self.stdout.write("No listings are currently due for a bump.")

                # Wait 30 seconds before checking listings again
                self.stdout.write("Cycle finished. Sleeping for 30 seconds...")
                time.sleep(30)

        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("Stopped."))
