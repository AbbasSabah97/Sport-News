# WorldPulse Football - Android

Android app with an original modern football-focused interface, inspired by the usability of live score apps, not copied proprietary FotMob branding or graphic assets.

Colors: orange #FF7730, indigo #1B2B5B, light background #F8F9FD. Arabic RTL layout and stable light theme even in Android Dark Mode.

Screens: Home, seven-day Matches, seven Competitions, Match Details, real Standings when available, Team Following, and Settings. Includes Iraqi Stars League, LaLiga, Premier League, UEFA Champions League, FIFA World Cup, UEFA EURO, AFC Asian Cup.

Data: hourly docs/feed.json from GitHub Actions. ESPN and TheSportsDB endpoints can be incomplete; optional API_FOOTBALL_KEY may improve coverage. Live statistics, lineups and standings are displayed only when sourced. The verified Iraqi Stars League snapshot from October 30, 2026 is time-limited.

No downloaded images or historical feed files stored on-device. Only followed team names are saved in SharedPreferences.

Build APK with .github/workflows/build-android.yml. Debug-signed APK is for testing, not Play Store publishing. Minimum Android 8.0.
