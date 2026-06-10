# PlayerUp Auto-Bumper Sync Extension

A companion Google Chrome extension for the PlayerUp Auto-Bumper system. It automatically harvests listing details and syncs credentials from the PlayerUp forum directly to your Django web dashboard.

## Features

- **Automated Listing Parser**: Auto-scrapes thread listings when you browse your recent content pages on PlayerUp.
- **Session Sync**: Extracts your active `xf_session` cookie securely and posts it to the backend to keep the background bumpers authenticated 24/7.
- **Real-Time Extension Badge**: Displays the count of scraped listings directly on the extension icon badge.
- **Interactive Popup**: Custom dark dashboard showing last sync time, connected status light, manual sync triggers, and options to modify the backend address.

## Installation

1. Open Google Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select the `playerup-extension` directory from your local computer files.
5. The extension will load, and you will see the yellow/green lightning bolt icon in your extension list!

## Getting Started

1. **Verify Django Backend Address**:
   - Click the extension icon in your Chrome toolbar.
   - By default, it is configured to point to `https://playerup-bumper-web.onrender.com`.
   - If you deploy your Django dashboard to **Render.com** or another cloud host, paste your server's web URL into the **Backend URL** input box at the bottom and click **Save**.

2. **Trigger Initial Synchronization**:
   - Open your popup panel and click **Sync Now**.
   - The extension will automatically open the PlayerUp account threads page.
   - When the page loads, the extension scrapes your listings and syncs them with your username and `xf_session` cookie to the dashboard.
   - A green confirmation banner will slide down at the top of the webpage, and a Chrome desktop notification will appear!

## Troubleshooting

- **"Connection Error" (Red Indicator)**:
  Make sure your Django web server is running and accessible. If running locally, check that the port matches (e.g. `http://127.0.0.1:8001`).
- **"Cookie Missing" Warning**:
  Ensure you are logged into your PlayerUp account on the forum page so the extension can capture the `xf_session` cookie.
