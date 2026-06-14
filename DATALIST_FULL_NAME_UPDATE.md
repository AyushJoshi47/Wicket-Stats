# Full-Name Input Mapping Update

Updated on: 2026-06-14 11:20:59 +05:30
Refined on: 2026-06-14 11:28:02 +05:30
Layer fix on: 2026-06-14 11:32:25 +05:30
Team autocomplete on: 2026-06-14 11:37:49 +05:30

## Initial change (11:20:59 +05:30)

1. Added one shared names source:
- Created `static/full_names_data.js`.
- This file exports `window.WS_FULL_NAMES` using the existing `full_names.json` data (768 names).

2. Updated `player_index` page:
- File: `templates/player_index.html`
- Added `list="player-names-list"` to the batter input.
- Added `<datalist id="player-names-list"></datalist>`.
- Included shared script: `/static/full_names_data.js`.
- Added JS to validate exact name match before submit.

3. Updated `bowler_index` page:
- File: `templates/bowler_index.html`
- Added `list="bowler-names-list"` to the bowler input.
- Added `<datalist id="bowler-names-list"></datalist>`.
- Included shared script: `/static/full_names_data.js`.
- Added JS to validate exact name match before submit.

4. Updated `comparison` page:
- File: `templates/comparison.html`
- Added `list="comparison-player-names-list"` to both player inputs.
- Added `<datalist id="comparison-player-names-list"></datalist>`.
- Included shared script: `/static/full_names_data.js`.
- Added JS to validate both names before submit.
- Blocked invalid names and same player comparison (case-insensitive).

## UI refinement (11:28:02 +05:30)

Based on visual feedback, native `<datalist>` was replaced with a custom styled autocomplete panel:

1. `templates/player_index.html`
- Removed native `datalist` usage.
- Added custom suggestion panel under batter input (`#player_name_suggest`).
- Added fixed-height, scrollable dropdown styling.
- Added keyboard navigation support (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`).

2. `templates/bowler_index.html`
- Removed native `datalist` usage.
- Added custom suggestion panel under bowler input (`#player_name_suggest`).
- Added fixed-height, scrollable dropdown styling.
- Added keyboard navigation support (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`).

3. `templates/comparison.html`
- Removed native `datalist` usage for both players.
- Added separate suggestion panels (`#player1Suggest`, `#player2Suggest`) directly below each input.
- Reduced input vertical size to better match page aesthetics.
- Added fixed-height, scrollable dropdown styling.
- Added keyboard navigation support (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`).

4. `static/full_names_data.js`
- Updated timestamp comment to reflect autocomplete-based usage.

## Z-index and layering fix (11:32:25 +05:30)

To ensure suggestions render above all cards:

1. `templates/player_index.html`
- Raised suggestions panel to `z-index: 999999`.
- Set `.pi-search-card`, `.pi-search-inputs-row`, and `.pi-search-inputs-wrapper` to allow visible overflow and proper stacking.

2. `templates/bowler_index.html`
- Raised suggestions panel to `z-index: 999999`.
- Set `.pi-search-card`, `.pi-search-inputs-row`, and `.pi-search-inputs-wrapper` to allow visible overflow and proper stacking.

3. `templates/comparison.html`
- Raised suggestions panel to `z-index: 999999`.
- Set `.wc-compare`, `.input-row`, and `.compare-input-wrap` to `overflow: visible` and higher stacking context.

## Team name autocomplete (11:37:49 +05:30)

Applied the same styled autocomplete behavior to team fields in batter and bowler index:

1. `templates/player_index.html`
- Added custom suggestion panel under `#team_name` (`#team_name_suggest`).
- Added IPL team master list in JS.
- Reused shared autocomplete logic for team suggestions.
- Added validation: if team is entered, it must match a known team name.

2. `templates/bowler_index.html`
- Added custom suggestion panel under `#team_name` (`#team_name_suggest`).
- Added IPL team master list in JS.
- Reused shared autocomplete logic for team suggestions.
- Added validation: if team is entered, it must match a known team name.

## Why this solves your issue

- Suggestions are now styled and open directly below each input (not side-floating native UI).
- Dropdown height is capped; additional names are scrollable.
- Invalid manual input is blocked before API calls.
- One shared list is reused across all three pages, so no duplicate hardcoded name arrays.

## Notes

- Timestamped update comments were added in each edited HTML file and in the shared JS file.
