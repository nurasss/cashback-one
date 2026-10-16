# Design QA — reference screen redesign

final result: passed

## Viewport and evidence

Compared the four supplied mobile references with the local Expo web preview at **390 × 844 CSS px**. The references are 845–852 × 1841–1849 px and have nearly the same aspect ratio.

- Home: [screenshot](mobile/screenshots/reference-redesign/home.png)
- Status: [screenshot](mobile/screenshots/reference-redesign/status.png)
- QR: [screenshot](mobile/screenshots/reference-redesign/qr.png)
- Profile: [screenshot](mobile/screenshots/reference-redesign/profile.png)

## Review

- **Home:** centered promo carousel with neighboring slide previews and dots, coral status and points panel, cashback line, two-column offer cards with separate artwork, and fixed bottom tabs.
- **Status:** glossy medal artwork with the level rendered from live data, points balance, progress to the next level, one existing action, and the shared bottom tabs.
- **QR:** dynamic QR remains generated from the current token; the screen uses the larger white panel and cashier instruction from the reference. The refresh timer is not shown.
- **Profile:** blank avatar, compact name fields, profile rows, red save action, and bottom tabs.

The local demo preview includes its existing test-data ribbon and does not draw the iOS status bar; those are runtime chrome rather than parts of the four screens. Native safe-area handling remains enabled.
