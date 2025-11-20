# Second Round Testing Checklist
**Created:** 2025-11-19
**Purpose:** Focused testing of recent changes and outstanding issues

---

## RECENT CHANGES TO TEST

### 1. Archive Pagination (NEW)
**Files Changed:** `calendarEditor/views.py`, `templates/calendarEditor/archive_list.html`

- [X] Navigate to `/schedule/archive/`
- [X] Verify page shows "Showing X-Y of Z entries" counter
- [X] Test per-page selector dropdown (10, 25, 50, 100)
  - [X] Select 10 → page shows max 10 entries
  - [X] Select 25 → page shows max 25 entries
  - [X] Select 50 → page shows max 50 entries
  - [X] Select 100 → page shows max 100 entries
- [X] Test pagination controls
  - [X] Previous/Next buttons work correctly
  - [X] Page numbers displayed correctly
  - [X] Current page highlighted
  - [X] Can jump to specific page number
- [X] Test filters with pagination
  - [X] Apply year filter → pagination still works
  - [X] Apply machine filter → pagination resets to page 1
  - [X] Filters preserved when changing pages
  - [X] Per-page setting preserved when filtering
- [BOTH EXPORT BUTTONS BROKEN: SERVER ERROR (500)] Test "Export All Measurements" button (should export ALL, not just current page)

---

### 2. Global Tooltip System (NEW)
**Files Changed:** `static/css/tooltips.css`, `static/js/tooltips.js`, `templates/base.html`, `home.html`, `fridge_list.html`
- [FIXED] /
#### Desktop Testing
- [X] Visit `/` (home page) while logged in
- [X] Find running measurement with tooltip
- [X] **Hover** over measurement title → tooltip appears
- [X] Tooltip shows full description (not truncated)
- [X] Tooltip has nice styling (dark background, arrow, readable)
- [X] Move mouse away → tooltip disappears
- [FIXED: When the thing is clicked, the tooltip doesn't go away until clicked again on desktop. On mobile, it never goes away, but I want it to go away when scrolling away or tap somewhere else.] Click for tooltip
#### Mobile/Tablet Testing
- [X] Open site on mobile device or use browser dev tools (responsive mode)
- [X] **Tap** on measurement title with tooltip
- [X] Tooltip appears and stays visible
- [FIXED: When the thing is clicked, the tooltip doesn't go away until clicked again on desktop. On mobile, I want it to go away also when scrolling away, not just tapping somewhere else.] Tap measurement again → tooltip disappears. 
- [X] Tap outside tooltip → tooltip disappears
- [X] Test on `/schedule/fridges/` page as well

#### Tooltip Locations to Test
- [X] Home page - "Running:" section (authenticated)
- [X] Home page - "Running:" section (unauthenticated)
- [X] Home page - "Currently Running:" yellow box
- [X] Fridge list - "Running:" in details (authenticated)
- [X] Fridge list - "Running:" in details (unauthenticated)
- [FIXED: Tooltip needs to be displayed over top and within the card or window that it's in. Right now it can extend beyond the frame but it's underneath so it's not entirely visible everywhere.] Tooltip text display perfectly.
#### Tooltip Content Validation
- [X] Create queue entry with 50+ character description
- [X] Check in to start measurement
- [X] Verify tooltip shows FULL description (not truncated like title)
- [FIXED] Test with very long description (200+ chars) → tooltip should wrap properly
- [FIXED: Can we also add tool tip for the on deck description in both the home page and the fridge specs and the admin queue locations, the same way? But also, I need it to say Description: and then the description.]

---

### 3. Measurement Description - 50 Character Minimum (NEW)
**Files Changed:** `calendarEditor/models.py`, `calendarEditor/forms.py`, migration `0033`

- [X] Navigate to `/schedule/submit/`
- [X] Fill out form with description < 50 characters
- [X] Submit → should see error "Not long enough (minimum 50 characters)"
- [X] Fill description with exactly 50 characters → should submit successfully
- [X] Verify help text shows example: "2D sweep from -10V to +10V..."
- [X] Test with existing entries (migration should have applied)
  - [X] View existing queue entries → no errors
  - [X] Edit existing entry → can save with current description if ≥50 chars

#### Validation Testing
- [X] Leave description blank → should see "This field is required"
- [X] Enter 49 characters → error
- [X] Enter 50 characters → success
- [X] Enter 500 characters → success
- [X] Enter 501 characters → should see max length error

---

### 4. Queue Cancel Notification Fix (MODIFIED)
**Files Changed:** `calendarEditor/notifications.py`

**Test Scenario:** Position #1 entry should NOT be notified when someone behind them gets cancelled

#### Setup
- [X] Create machine with 3 queue entries:
  - Position 1: User A
  - Position 2: User B
  - Position 3: User C

#### Test 1: Cancel Position 2 (A stays in position 1)
- [X] Admin cancels Position 2 (User B)
- [FIXED: No notification received] User B receives cancellation notification ✓
- [X] User A should **NOT** receive "you're in position 1" notification (already there)
- [FIXED: No notification received about the moving to pos N because a measurement ahead of them was cancelled.] User C receives "you moved to position 2" notification ✓

#### Test 2: Cancel Position 1 (New person becomes #1)
- [X] Admin cancels Position 1 (User A)
- [FIXED: No notification received.] User A receives cancellation notification ✓
- [FIXED: Double notification received for the pos 1] User C (now position 1) **SHOULD** receive notification (newly in position 1)
- [FIXED: Not reflecting either case whenever this is happening, except for when a user checks out like normal or is checked out by admin] Check if notification reflects machine status:
  - [Works for normal] If machine idle → "Ready for check-in" notification
  - [Works for normal] If machine running → "On deck" notification

---

### 5. Private Presets Alphabetization (MODIFIED)
**Files Changed:** `calendarEditor/admin_views.py`

- [X] Navigate to `/schedule/admin-presets/`
- [X] Check "Private Presets" section
- [X] Verify sorted by:
  1. **Author username** (alphabetically, case-insensitive)
  2. **Preset name** (alphabetically, case-insensitive)
- [X] Create test scenario:
  - User "zebra" with preset "AAA"
  - User "alpha" with preset "ZZZ"
  - User "alpha" with preset "AAA"
- [X] Expected order:
  1. alpha - AAA
  2. alpha - ZZZ
  3. zebra - AAA
- [X] Test with mixed case usernames (Alice, bob, Charlie)
- [X] Verify case-insensitive sorting works

---

## CRITICAL OUTSTANDING ISSUES

### 6. Admin Users Layout (NOT COMPLETE)
**Issue:** From TODO BATCH 4, item 2

**Requirements:**
- [X] Navigate to `/schedule/admin-users/`
- [X] Verify layout has 2 sections (vertically scrollable):
  1. **Unapproved Users** (Pending or Rejected status)
  2. **Active Users** (Approved status)
- [X] Each section should be horizontally scrollable (not extending beyond border)
- [X] Verify button sizes:
  - [X] All buttons same horizontal size
  - [X] All buttons same vertical size
  - [X] Reject/Delete buttons are red (danger color)
  - [X] Approve/Promote buttons are standard color
- [X] Test actions:
  - [X] Pending → can Approve or Reject
  - [X] Rejected → can Approve or Delete
  - [Well the order is unapprove, delete, confirm delete] Approved → can Unapprove or Delete
- [X] Alphabetized by username in each section

---

### 7. Rush Job Rejection with Custom Message (NOT COMPLETE)
**Issue:** From TODO BATCH 4, item 5
- [FIXED: Rush jobs is not text wrapping the title and sescription properly always. It will sometimes extend beyong the card's boundary. Bad. It needs to wrap here.]
- [FIXED: Relatedly, in /check-in-check-out, the title and description tests need to wrap instead of extending beyond the card boundary. This error is also causing the button to potentially appear in the wrong place.]
- [FIXED: Relatedly, in the home page and in /fridges, the tool tip containing the measurement description needs to wrap and be inside of the boundary as mentioned somewhere else in this document.]
- [FIXED: Relatedly, in archive, under Notes, the description should truncate and have a tooltip with a wrapped version of the description in a way that makes sense.]

- [X] Submit rush job as regular user
- [X] Navigate to `/schedule/admin-rush-jobs/` as admin
- [X] Click "Reject" button
- [X] Verify modal appears with:
  - [X] Default message: "Insufficient justification"
  - [FIXED: I want the Insufficient justification to be a typehint there so that when clicked, it goes away and the custom message can be written without needing to first delete the suggested message. Otherwise it's working.] Text area to write custom message
  - [X] "Reject" button (red/danger)
  - [X] "Back" button (NOT "Cancel")
- [X] Test default message:
  - [X] Don't modify text → click Reject
  - [X] User receives notification with "Insufficient justification"
- [X] Test custom message:
  - [X] Write custom reason → click Reject
  - [X] User receives notification with custom reason
- [X] Test "Back" button:
  - [X] Click Back → modal closes, no action taken
  - [X] Entry still pending

---

### 8. Machine Deletion with Queue Entries (NOT COMPLETE)
**Issue:** From TODO BATCH 4, item 7

#### Test Scenario 1: Machine with Active Entries
- [X] Create machine with 2 queued entries
- [X] Navigate to `/schedule/admin-machines/`
- [X] Click "Delete" on machine
- [X] Should see confirmation dialog:
  - Message: "QUEUE ENTRIES DETECTED → IT HAS 2 active QUEUE ENTRIES"
  - Question: "ARE YOU SURE YOU WOULD LIKE TO DELETE MACHINE X?"
  - Buttons: "YES, DELETE" (red) and "NO, CANCEL" (gray)
- [X] Click "NO, CANCEL" → machine not deleted
- [X] Click "YES, DELETE" → machine deleted
- [X] Check affected users:
  - [FIXED: Was not received.] Users with entries receive "orphaned entry" notification
  - [FIXED: Was not received] Notification explains machine was deleted
  - [FIXED: Machine name in archive shows as blank. Status should be showing Orphaned, with tool tip Machine was deleted. Instead it shows Orphaned (Machine Deleted).] Entries show machine name as "[DELETED] MachineName"

#### Test Scenario 2: Machine with Only Archived Entries
- [X] Create machine, complete 1 measurement (archived)
- [X] No active queue entries
- [X] Click "Delete" → should delete immediately (no warning)
- [FIXED: Name field is shown as empty. Status needs to add a tooltip to Completed or Cancelled: Machine was deleted.] Verify archive still shows machine name correctly

#### Test Scenario 3: New Machine Entry Not Showing in Archive
**Bug to fix:** "The database isn't set up to handle a new machine"
- [X] Create NEW machine (never used before)
- [X] Submit queue entry for new machine
- [X] Check in → Check out
- [X] Navigate to `/schedule/archive/`
- [X] **Verify entry appears in archive** (this is the bug - currently doesn't show)

---

### 9. Notification for Followed Preset Updates (NOT WORKING)
**Issue:** From checklist line 513

- [X] User A creates public preset "Test Preset"
- [X] User B follows "Test Preset"
- [X] User A edits preset (changes name or fields)
- [X] User B should receive notification: "Preset you follow was updated"
- [X] **Currently:** Not working - fix and test

---

### 10. Export All Measurements Button (NEEDED)
**Issue:** From TODO line 437

- [X] Navigate to `/schedule/archive/` as **regular user** (non-staff)
- [X] Verify "Export All Measurements" button exists
- [FIXED] Click button → CSV downloads
- [N/A] Open CSV → contains ALL measurements (not just user's)
- [N/A] Verify columns include:
  - [N/A] ID, Machine, Date, Title, Notes, Duration, Archived At
  - [FIXED: Not tracking Duration for new measurements] **Duration field should be populated** (from recent migration)

---

## EDGE CASES & REGRESSIONS

### 11. Username Validation (MODIFIED)
**Change:** Removed username validators to allow spaces/special characters

- [X] Navigate to `/register/`
- [X] Test username with spaces: "John Doe" → should work
- [X] Test username with special chars: "test@user!" → should work
- [X] Test username with emoji: "user🎉" → should work
- [X] Verify usernames still case-sensitive unique check
- [X] Duplicate username (different case) → should show error

---

### 12. Countdown Timers (RECENTLY MODIFIED)
**Files:** `home.html`, `fridge_list.html`

- [X] Start a running measurement (check in)
- [X] Navigate to home page
- [X] Find "Currently Running" section
- [X] Verify countdown shows: "Xh Ym remaining" (NOT "Calculating...")
- [X] Wait 1 minute → countdown updates in real-time
- [X] Navigate to `/schedule/fridges/`
- [FIXED: In /fridges, for a split second after loading, the status shows the Disconnected - measuring or whatever more bold. Then the formatting updates to make the colors different. It should keep the colors in the original formatting and not change them to the pale background with red text or whatever. Match the colors and text of the status in the home page.] Status fix
- [It feels like maybe it's not calculating based on the measurement time] Expand machine details → verify countdown works there too
- [X] Test when measurement completes:
  - [X] Countdown should show "Completed" (in green color)

---

### 13. Position #1 Notification Based on Machine Status (CRITICAL)
**Issue:** From TODO line 529, TODO BATCH 4 item 3

**Test when entry reaches position #1:**

#### Scenario A: Machine is Idle/Available
- [X] Set machine status to "idle"
- [X] Set machine as available (not in maintenance)
- [X] Move entry to position 1
- [FIXED: User received the ON DECk notification instead of Ready for Check in notification.] User receives: **"Ready for Check-In"** notification
- [X] Notification is marked CRITICAL (cannot disable)
- [X] Includes check-in link

#### Scenario B: Machine is Running
- [X] Machine has running measurement
- [X] Move different entry to position 1 (in queue)
- [X] User receives: **"On Deck"** notification (NOT ready yet)
- [X] Notification explains machine is busy

#### Scenario C: Machine in Maintenance
- [X] Set machine to maintenance mode
- [X] Move entry to position 1
- [X] User receives: **"On Deck"** notification
- [BROKEN: Not stated. Just an on deck, get ready notification.] Message explains machine in maintenance
- [FIXED: The undo check in button for a measurement that was already running when a machine is put in maintenance by admin needs to be disabled. And it needs to NOT change the machine status from maintenance to idle, even if the request gets through. The machine status should change to (Dis)Connected - Maintenance in the home page, fridges page, and admin machine pages, and relevant queue locations.]
- [FIXED: Maybe the solution is just make the machine unavailable when it is in maintenance, so when the admin selects maintenance, also deselect the is available. That should be an easy script to put in.]
#### Scenario D: Machine in Cooldown
- [TODO] Machine has estimated_available_time in future
- [TODO] Move entry to position 1
- [TODO] User receives: **"On Deck"** notification
- [TODO] Message may include estimated available time

---

### 14. Slack vs Email Notifications (TODO)
**Issue:** From checklist line 527-528

- [X] User without Slack ID configured
- [X] Trigger notification (e.g., reach position 1)
- [X] **Currently:** Only in-app notification sent
- [TODO] **Should:** Email notification sent (if email notifications enabled)
- [TODO] **Fix:** Implement email fallback when Slack ID missing

---

### 15. Undo Check-In Button (TODO)
**Issue:** From checklist line 351 and TODO BATCH 3 item 1

- [X] Check in to measurement
- [X] Navigate to `/schedule/check-in-check-out/`
- [X] Find "Currently Running" section
- [X] **Currently:** May have "Undo Check-In" button
- [X] Click "Undo Check-In" → should work without 500 error
- [X] Verify:
  - [X] Status changes back to "queued"
  - [X] Machine status resets to "idle"
  - [X] Reminder is cancelled
  - [X] User notified about undo
  - [X] Next person in queue **should NOT** get position 1 notification (since first person is back)

---

### 16. Admin Edit Form Routing (TODO)
**Issue:** From TODO BATCH 4, item 6

- [X] Navigate to `/schedule/admin-queue/`
- [X] Click "Edit" on any entry
- [X] Make changes → click "Save Changes"
- [FIXED: When editing from rush job, it goes back to admin-queue when edited or cancelled.]  **Should route to:** `/schedule/admin-rush-jobs/` (if was rush job) OR stay on admin-queue
- [FIXED: When editing an entry, the machine reassignment is wacked out. If it can stay on the same machine, it should. If it can't, then a clearer message as to what it can be assigned to because of the changes made should be given. But right now, it's not selecting properly, since it wanted to move one from one it was fine on to another one it was fine on, but it should have stayed with the original. Also in that field, the checkboxes need to match the checkbox formatting in other pages, like submit queue entry form.]
- [FIXED: Machine reassignment is not being applied. It finds the correct ones that it CAN be switched to, but it doesn't switch the assignement from the rush job page like it should be doing.]
- [FIXED: When admins are reordering the queue, the moved from N to N is just saying moved from 1 to N, instead of (what it is now - 1) to (what it is now).]
- [FIXED: The entries are taking up more horizontal space than allotted in the blue boundary for the card. Make them horizontall scrollable cards and collapsable (with just the machine and (N entries) visible), collapsed by default. Finally, the buttons need to be of uniform size as following: Edit/Cancel/Start/Check Out/Undo Check-In match vertically in size. Check Out/Undo Check-in, Waiting, Move to First need to all be the same horizontal size, even if not all of them are being displyed in a card, so that the machine cards have consistent and aligned button locations. Up and down arrows will thus be the same correct size and location to make all the buttons aligned correctly and pretty. Right now they are all text-dependent to make them the size they are, but they need to be as long as they need to be to fit the text and match the ones they need to match. Title needs to truncate to a specific char value to stop the entries from being too long horizontally, but it shouldn't need to text-wrap more than 3 lines, since we can take up more space horizontally if it scrolls horizontally. Finally, the running entry should have the grayed out version of up and down arrows. Thank you.]

---

### 17. Private Preset Delete Dialog (TODO)
**Issue:** From checklist line 428, 497

- [X] As **regular user**, create private preset
- [X] Click "Delete" on YOUR preset
- [X] Should see **normal confirmation** dialog (not Thanos modal)
- [X] As **admin**, delete public preset
- [FIXED: See line below this] Should see **Thanos snap dialog** (dramatic confirmation)
- [FIXED: In schedule/submit, admin sees normal delete dialog. In admin-presets, dialog is correct for public presets but the private presets is the "page says" thing, not even custom dialog.] Verify both work correctly

---

### 18. Concurrent Edit Protection (TODO)
**Issue:** From checklist line 1147

- [X] Open admin-queue in two browser tabs
- [X] Tab 1: Click "Edit" on entry #5
- [X] Tab 2: Click "Delete" on entry #5
- [X] Tab 2: Confirm deletion
- [X] Tab 1: Try to save changes
- [X] **Should:** Show error banner "Entry no longer exists" + reload page
- [No it worked just fine] **Currently:** May show 500 error or crash
- [It worked just fine] **Fix:** Add try/except in save logic
- [FIXED: QUEUE ENTRIED SHOULD NEVER BE DELETED OUTRIGHT. THEY SHOULD JUST BE ARCHIVED AS CANCELLED. Not currently what is happening.]

---

## QUICK SMOKE TESTS

### Core Functionality (Must Work)
- [X] Register new account → success
- [X] Login → success
- [X] Submit queue entry → appears in My Queue
- [X] Check in → status changes to "Running"
- [X] Check out → status changes to "Completed"
- [FIXED: Undo Check in should only display thanos dialog for staff. Regular users should see the default custom dialogue.]
- [BROKEN: Make Check out and Undo-Check in the same size horizontally and vertically, not just text determined size.]
- [X] Archive appears with entry
- [X] Admin can approve user
- [X] Admin can cancel entry
- [X] Notifications appear in notification page

---

## KNOWN ISSUES TO DOCUMENT

Document any new bugs found during testing:

### Issue 1: [Title]
- **Severity:** Critical / High / Medium / Low
- **Steps to Reproduce:**
  1.
  2.
  3.
- **Expected:**
- **Actual:**
- **Workaround:**

### Issue 2: [Title]
...

---

## TESTING NOTES

**Tester:** ________________
**Date:** ________________
**Environment:** Local / Production

**Browsers Tested:**
- [X] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Mobile Chrome/Safari
**Critical Issues Found:** ______

**Can Deploy?** YES / NO / [WITH CAVEATS]

**Notes:**
_________________________________________________________________
_________________________________________________________________

---

**END OF SECOND ROUND TESTING**
