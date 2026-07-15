import os
import sys
import django

# Set up Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playerup_dashboard.settings')
django.setup()

from bumper.models import Listing, BumpLog

def run():
    print("Scanning log database for upgrade redirects...")
    logs = BumpLog.objects.filter(message__icontains="Requires paid upgrades")
    print(f"Found {logs.count()} matched logs.")
    
    updated_count = 0
    for log in logs:
        listing = log.listing
        if listing.status != 'requires_upgrade':
            listing.status = 'requires_upgrade'
            listing.bump_enabled = False
            listing.save()
            print(f"Moved to Upgrade Page: {listing.title[:50]}... (ID: {listing.id})")
            updated_count += 1
            
    print(f"Done. Retroactively moved {updated_count} listings.")

if __name__ == '__main__':
    run()
