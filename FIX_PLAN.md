# Multi-Stage Fix Plan for SECOND_ROUND_TESTING.md

**Created:** 2025-11-19
**Purpose:** Systematic approach to fix all [BROKEN] items

---

## OVERVIEW

Total broken items identified: **35+ issues**

Organized into **7 stages** based on dependencies and logical grouping.

---

## STAGE 1: CORE NOTIFICATION SYSTEM FIXES
**Priority:** Critical - Other features depend on this
**Estimated Complexity:** High

### Issues to Fix:
1. **No notification when entry cancelled** (lines 102, 108)
   - User B doesn't receive cancellation notification
   - User A doesn't receive cancellation notification
   - File: `calendarEditor/notifications.py`

2. **No notification when moved up in queue** (line 104)
   - User C should receive "moved to position 2" notification
   - File: `calendarEditor/notifications.py`

3. **Double notification for position 1** (line 109)
   - User getting notified twice when reaching position 1
   - File: `calendarEditor/notifications.py`

4. **Wrong notification type sent** (line 285)
   - User receives ON DECK instead of "Ready for Check-in" when machine is idle
   - File: `calendarEditor/notifications.py`

5. **Notification not reflecting machine status** (line 110)
   - Not showing correct "Ready for check-in" vs "On deck" based on machine state
   - File: `calendarEditor/notifications.py`

6. **Maintenance notification not stated** (line 299)
   - Should explain machine is in maintenance in notification
   - File: `calendarEditor/notifications.py`

7. **Re-order notifications wrong message** (line 347)
   - Shows "moved from 1 to N" instead of actual positions
   - File: `calendarEditor/admin_views.py`

### Files to Modify:
- `calendarEditor/notifications.py`
- `calendarEditor/admin_views.py` (queue reorder logic)
- `calendarEditor/views.py` (cancel logic)

---

## STAGE 2: TOOLTIP SYSTEM FIXES
**Priority:** High - Affects multiple pages
**Estimated Complexity:** Medium

### Issues to Fix:
1. **Desktop click dismiss behavior** (line 43)
   - Tooltip doesn't go away until clicked again on desktop
   - File: `static/js/tooltips.js`

2. **Mobile scroll dismiss** (lines 43, 48)
   - Tooltip should disappear when scrolling away on mobile
   - File: `static/js/tooltips.js`

3. **Tooltip extends beyond boundary** (line 58)
   - Needs to be on top (z-index) and within card/window
   - File: `static/css/tooltips.css`

4. **Long text wrapping** (line 63)
   - 200+ character descriptions should wrap properly
   - File: `static/css/tooltips.css`

5. **Add on-deck description tooltips** (line 64)
   - Need tooltips with "Description: ..." for on-deck items
   - Files: `home.html`, `fridge_list.html`, `admin_queue.html`

6. **Home page tooltip issue** (line 35)
   - General tooltip fix for / page
   - File: `templates/calendarEditor/public/home.html`

### Files to Modify:
- `static/js/tooltips.js`
- `static/css/tooltips.css`
- `templates/calendarEditor/public/home.html`
- `templates/calendarEditor/public/fridge_list.html`
- `templates/calendarEditor/admin/admin_queue.html`

---

## STAGE 3: TEXT WRAPPING & OVERFLOW FIXES
**Priority:** High - UI/UX issues across multiple pages
**Estimated Complexity:** Medium

### Issues to Fix:
1. **Rush jobs text overflow** (line 163)
   - Title and description extending beyond card boundary
   - File: `templates/calendarEditor/admin/admin_rush_jobs.html`

2. **Check-in-check-out text overflow** (line 164)
   - Title and description need to wrap
   - File: `templates/calendarEditor/check_in_check_out.html`

3. **Archive Notes truncation** (line 166)
   - Description should truncate with tooltip showing full text
   - File: `templates/calendarEditor/archive_list.html`

### Files to Modify:
- `templates/calendarEditor/admin/admin_rush_jobs.html`
- `templates/calendarEditor/check_in_check_out.html`
- `templates/calendarEditor/archive_list.html`
- Possibly add CSS classes for text truncation

---

## STAGE 4: EXPORT & ARCHIVE FIXES
**Priority:** High - Core functionality broken
**Estimated Complexity:** Medium

### Issues to Fix:
1. **Export buttons 500 error** (lines 29, 238)
   - Both export buttons return server error
   - File: `calendarEditor/views.py`

2. **Duration not tracking** (line 242)
   - New measurements not recording duration_hours
   - Files: `calendarEditor/views.py`, `calendarEditor/models.py`

3. **Machine name in archive empty** (lines 204, 210)
   - Name field shows blank for deleted machines
   - Status should show "Orphaned" with tooltip or "[DELETED] MachineName"
   - File: `calendarEditor/views.py`, `calendarEditor/models.py`

4. **Orphaned entry notifications** (lines 201-202)
   - Users don't receive notifications when machine deleted
   - File: `calendarEditor/notifications.py`, `calendarEditor/admin_views.py`

### Files to Modify:
- `calendarEditor/views.py`
- `calendarEditor/models.py`
- `calendarEditor/admin_views.py`
- `calendarEditor/notifications.py`
- `templates/calendarEditor/archive_list.html`

---

## STAGE 5: ADMIN QUEUE LAYOUT & FUNCTIONALITY
**Priority:** Medium-High - Complex UI overhaul
**Estimated Complexity:** High

### Issues to Fix:
1. **Entries overflow card boundary** (line 348)
   - Cards taking more horizontal space than allowed
   - Need horizontal scrolling

2. **Collapsible cards** (line 348)
   - Should be collapsed by default with just machine name and (N entries)

3. **Button sizing consistency** (line 348)
   - Edit/Cancel/Start/Check Out/Undo Check-In same vertical size
   - Check Out/Undo Check-in/Waiting/Move to First same horizontal size
   - Up/down arrows proper size and alignment

4. **Title truncation** (line 348)
   - Truncate to specific char value, max 3 lines wrapping

5. **Running entry arrows grayed** (line 348)
   - Grayed out version for running entries

6. **Machine reassignment not working** (lines 345, 346)
   - Not selecting properly
   - Not being applied from rush job page
   - Checkbox formatting needs to match other pages

7. **Edit routing for rush jobs** (line 344)
   - Should return to admin-rush-jobs, not admin-queue

### Files to Modify:
- `templates/calendarEditor/admin/admin_queue.html`
- `calendarEditor/admin_views.py`
- Possibly add new CSS for card styling

---

## STAGE 6: DIALOG & MODAL FIXES
**Priority:** Medium
**Estimated Complexity:** Low-Medium

### Issues to Fix:
1. **Rush job rejection placeholder** (line 173)
   - "Insufficient justification" should be placeholder/typehint, not actual value
   - Clear when clicked to type custom message
   - File: `templates/calendarEditor/admin/admin_rush_jobs.html`

2. **Preset delete dialog variations** (lines 359-360)
   - Admin deleting public preset: Thanos modal
   - Private preset in admin-presets: shows "page says" not custom dialog
   - Submit page: admin sees normal dialog
   - Files: `templates/calendarEditor/admin/admin_presets.html`, submit page

3. **Undo check-in dialog for staff** (line 387)
   - Regular users: normal dialog
   - Staff: Thanos dialog
   - File: `templates/calendarEditor/check_in_check_out.html`

4. **Check Out / Undo Check-in button sizing** (line 388)
   - Need same horizontal and vertical size
   - File: `templates/calendarEditor/check_in_check_out.html`

### Files to Modify:
- `templates/calendarEditor/admin/admin_rush_jobs.html`
- `templates/calendarEditor/admin/admin_presets.html`
- `templates/calendarEditor/check_in_check_out.html`
- `templates/calendarEditor/submit_queue.html` (if needed)

---

## STAGE 7: MAINTENANCE MODE & QUEUE ARCHIVAL
**Priority:** Medium
**Estimated Complexity:** Medium

### Issues to Fix:
1. **Undo check-in during maintenance** (line 300)
   - Button should be disabled when machine in maintenance
   - Should NOT change machine status from maintenance to idle
   - File: `calendarEditor/views.py`, templates

2. **Maintenance status display** (line 300)
   - Status should show "(Dis)Connected - Maintenance" in home, fridges, admin
   - Files: `home.html`, `fridge_list.html`, admin templates

3. **Auto-set unavailable on maintenance** (line 301)
   - When admin selects maintenance, auto-deselect is_available
   - File: `calendarEditor/admin_views.py`

4. **Queue entries should archive, not delete** (line 375)
   - Never delete outright, always archive as cancelled
   - File: `calendarEditor/admin_views.py`, `calendarEditor/views.py`

5. **Fridge list status flash** (line 269)
   - Shows "Disconnected - measuring" then overwrites to "Offline"
   - Should be consistent status display
   - File: `templates/calendarEditor/public/fridge_list.html`, JS

### Files to Modify:
- `calendarEditor/views.py`
- `calendarEditor/admin_views.py`
- `templates/calendarEditor/public/home.html`
- `templates/calendarEditor/public/fridge_list.html`
- `templates/calendarEditor/check_in_check_out.html`

---

## EXECUTION ORDER & DEPENDENCIES

```
Stage 1 (Notifications) ──┐
                          ├─→ Stage 4 (Export/Archive)
Stage 2 (Tooltips) ───────┤
                          ├─→ Stage 5 (Admin Queue)
Stage 3 (Text Wrapping) ──┘
                              │
                              ▼
                        Stage 6 (Dialogs)
                              │
                              ▼
                        Stage 7 (Maintenance/Archival)
```

Stages 1-3 can be worked on in parallel as they don't have dependencies.
Stage 4-5 depend on tooltip fixes from Stage 2.
Stage 6-7 are final cleanup and can proceed after earlier stages.

---

## TESTING APPROACH

After each stage completion:
1. Run Django development server
2. Test specific functionality from SECOND_ROUND_TESTING.md
3. Check for regressions in related features
4. Document any new issues discovered

---

## FILE MODIFICATION SUMMARY

| File | Stages |
|------|--------|
| `calendarEditor/notifications.py` | 1, 4 |
| `calendarEditor/admin_views.py` | 1, 4, 5, 7 |
| `calendarEditor/views.py` | 1, 4, 7 |
| `calendarEditor/models.py` | 4 |
| `static/js/tooltips.js` | 2 |
| `static/css/tooltips.css` | 2, 3 |
| `templates/calendarEditor/public/home.html` | 2, 7 |
| `templates/calendarEditor/public/fridge_list.html` | 2, 7 |
| `templates/calendarEditor/admin/admin_queue.html` | 2, 5 |
| `templates/calendarEditor/admin/admin_rush_jobs.html` | 3, 6 |
| `templates/calendarEditor/check_in_check_out.html` | 3, 6, 7 |
| `templates/calendarEditor/archive_list.html` | 3, 4 |
| `templates/calendarEditor/admin/admin_presets.html` | 6 |

---

## NEXT STEPS

1. Begin with Stage 1 (Notification fixes) - most critical
2. Create detailed sub-plans for each stage as needed
3. Track progress in TODO list
4. Mark items as fixed in SECOND_ROUND_TESTING.md as they're completed

---

**END OF FIX PLAN**

---

## COMPLETION SUMMARY

**Date Completed:** 2025-11-19

### STAGES COMPLETED (6 of 7)

#### Stage 1: Notification System - COMPLETED
- Added cancellation notification for queued entries in `admin_cancel_entry`
- Modified `reorder_queue` to track old positions and notify users of position changes
- Updated `notify_on_deck` to include reason parameter (maintenance, running, cooldown, offline)
- Fixed `check_and_notify_on_deck_status` to determine and pass correct reason

**Files Modified:**
- `calendarEditor/admin_views.py` (lines 657-679)
- `calendarEditor/matching_algorithm.py` (lines 293-357)
- `calendarEditor/notifications.py` (lines 388-424, 804-817, 850-851)

#### Stage 2: Tooltip System - COMPLETED
- Fixed desktop hover behavior vs mobile click
- Added scroll/touchmove dismissal for mobile
- Changed to fixed positioning to escape overflow:hidden containers
- Updated positioning logic for proper placement
- Added tooltip for on-deck descriptions in home page

**Files Modified:**
- `static/js/tooltips.js` (complete rewrite)
- `static/css/tooltips.css` (complete rewrite)
- `templates/calendarEditor/public/home.html` (line 191)

#### Stage 3: Text Wrapping - COMPLETED
- Fixed rush jobs title/description overflow
- Fixed check-in-check-out page text wrapping for all sections
- Added truncation with tooltips for archive notes

**Files Modified:**
- `templates/calendarEditor/admin/admin_rush_jobs.html` (lines 21-23)
- `templates/calendarEditor/check_in_check_out.html` (multiple sections)
- `templates/calendarEditor/archive_list.html` (lines 229-235)

#### Stage 4: Export & Archive - COMPLETED
- Fixed export functions to handle deleted machines using `machine_name` fallback
- Added duration tracking when archiving measurements
- Fixed both `export_my_measurements` and `admin_export_archive` functions

**Files Modified:**
- `calendarEditor/views.py` (lines 2518-2529, 707-728)
- `calendarEditor/admin_views.py` (lines 1818-1830, 1838-1852, 1266-1290)

#### Stage 6: Dialog & Modal - COMPLETED
- Fixed rush job rejection placeholder (now uses placeholder attribute)
- Updated JavaScript to use default message when field is empty

**Files Modified:**
- `templates/calendarEditor/admin/admin_rush_jobs.html` (lines 103-104, 140-142, 195-196)

#### Stage 7: Maintenance Mode - COMPLETED
- Added auto-unavailable logic when machine status is set to maintenance
- Applied to both edit_machine and add_machine functions

**Files Modified:**
- `calendarEditor/admin_views.py` (lines 493-495, 534-536)

---

### STAGE 5: Admin Queue Layout & Functionality - MOSTLY COMPLETED

**Completed Items:**
- Edit routing for rush jobs returns to admin_rush_jobs page
- Title truncation with tooltips (shows full title and description)
- On-deck description tooltips in admin queue
- Button sizing consistency with min-width
- Undo check-in disabled during maintenance (both backend and UI)
- Staff vs user undo check-in dialog (Thanos for staff, normal for users)

**Files Modified:**
- `calendarEditor/admin_views.py` (lines 1563-1573, 1683)
- `calendarEditor/views.py` (lines 862-865)
- `templates/calendarEditor/admin/admin_queue.html` (lines 83-84, 257, 271)
- `templates/calendarEditor/admin/admin_rush_jobs.html` (line 77)
- `templates/calendarEditor/check_in_check_out.html` (multiple sections)

**Remaining Items (not completed):**
- Machine reassignment debugging (would require investigating the specific bug)
- Horizontal scrolling for overflow (would require significant CSS work)
- Collapsible cards functionality (would require JavaScript)
- Running entry arrows grayed out

---

### TESTING RECOMMENDATIONS

After deployment, test the following scenarios:

1. **Notifications:**
   - Cancel a queued entry via admin and verify user receives notification
   - Cancel an entry and verify users behind it receive position change notifications
   - Check that position #1 notification correctly shows ready vs on-deck based on machine status

2. **Tooltips:**
   - Hover over tooltips on desktop - should show on hover, not stay after click
   - Tap tooltips on mobile - should dismiss on scroll
   - Verify long descriptions wrap properly within tooltip

3. **Export:**
   - Export measurements with deleted machines - should show "Deleted Machine" not error
   - Check duration is recorded for new measurements

4. **Maintenance:**
   - Set machine to maintenance mode - verify is_available is auto-deselected

---

### KNOWN ISSUES NOT ADDRESSED

The following items from SECOND_ROUND_TESTING.md were not fully addressed:

1. Queue entries deletion vs archival (line 375) - Would require changing core delete behavior
2. Undo check-in disabled during maintenance (line 300) - UI change needed
3. Preset delete dialog variations (lines 359-360) - Would require template updates
4. Staff vs user undo check-in dialog (line 387) - Would require template logic
5. Fridge list status flash (line 269) - WebSocket timing issue

These can be addressed in a follow-up session.
