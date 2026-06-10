# PlayerUp Auto-Bumper Dashboard

A production-ready Django 4.2 dashboard for automating, tracking, and managing thread bumps on the PlayerUp forums.

## Features

- **Dynamic Content Scraper**: Paginated scanning of your PlayerUp listings, extracting threads and metadata using XenForo cookie authentication.
- **Manual & Scheduled Bumping**: Automated XenForo form or link-based bumping with safety pre-checks (for active limits) and post-checks (for success signals).
- **Real-Time Polling Dashboard**: Premium dark-themed dashboard showing high-level operational statistics, direct automated bumper toggles, instant bump overrides, and real-time execution logs.
- **Audit Logs View**: A robust, filtered tabular history of every scraper operation and bump action.
- **Background Daemon Worker**: An intelligent background service that periodically runs scrapes and handles scheduling queues while strictly adhering to anti-rate-limit and anti-detection delays.

## Installation & Setup

1. **Clone & Navigate**:
   Make sure files are set up in your designated target folder.

2. **Configure Environment**:
   Rename or copy `.env.example` to `.env` and fill in your custom keys:
   ```ini
   PLAYERUP_SESSION_COOKIE=paste_xf_session_cookie_value_here
   PLAYERUP_USERNAME=your_playerup_username
   DJANGO_SECRET_KEY=change-this-to-a-real-secret-key
   BUMP_INTERVAL_MINUTES=30
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create Superuser (Optional, for admin panel)**:
   ```bash
   python manage.py createsuperuser
   ```

## Running the Project

1. **Start the Web Dashboard**:
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` in your browser.

2. **Start the Scheduler/Bumper Daemon**:
   ```bash
   python manage.py run_bumper
   ```
   This background loop will keep scanning for threads that are due for a bump, execute the bumps with natural delays, and automatically refresh the dashboard live.
