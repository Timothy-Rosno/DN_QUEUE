# Comprehensive Testing Checklist - Queue Management System

**Purpose:** Test every feature, page, and user interaction to identify bugs and verify functionality.

**Testing Approach:** Work through each section systematically, checking off items as you verify they work.

---

## Testing Setup

## UPDATE PROGRESS
TODO BATCH 1: 
1. OK   Guard schedule/queue with @login 
2. Slack notif for account approval/status changes
3. OK   Remember me checkbox fix
4. Fix login behavior for unapproved accounts
5. OK   Fixed recover-username edge case (multiple usernames per email)
6. OK   Contact admin for specific profile info changes
7. OK   Create admin way to make said changes
8. Check in/check out undo checkin
9. Allow admins to edit running entries.
Extra info: Notifications are set up only for slack and the web version at the moment, not email. 
Test especially that the web notification works.




### Test User Accounts Needed

Create these accounts for testing:
- [TODO] Add admin only button in Queue status that routs admins to the /schedule/admin-queue
- [X] **Test Admin** - Username: `test_admin` - Staff status: YES
- [X] **Test User 1** - Username: `test_user1` - Approved, not staff
- [X] **Test User 2** - Username: `test_user2` - Approved, not staff
- [X] **Test User 3** - Username: `test_unapproved` - NOT approved yet
- [X] **Test User 4** - Username: `test_user_slack` - With Slack ID configured (if testing Slack)

### Test Data Setup

- [X] At least 3 machines configured (different names, statuses)
- [X] At least 5 queue entries in various states (pending, ready, running, completed)
- [X] At least 3 presets created by different users
- [X] Some archived measurements

---

## 1. GUEST/UNAUTHENTICATED USER TESTING

### Homepage (`/`)

- [X] Visit homepage without being logged in
- [X] See welcome message and description
- [TODO] Click "View Public Queue" link → redirects to `/schedule/queue/` NOT GUARDED BUT SHOULD BE UNLESS WANT QUEUE VISIBLE TO PUBLIC. I THINK NEED LOGIN IS BETTER?
- [TODO] Change text to Login to view queue entries
- [X] Click "View Lab Fridges" link → redirects to `/schedule/fridges/`
- [X] Click "Login" button → redirects to login page
- [X] Click "Register" button → redirects to registration page
- [X] No admin links visible


### Public Queue Page (`/schedule/queue/`)

- [X] View queue without login
- [X] See all pending and running queue entries
- [X] See machine assignments
- [X] See estimated durations
- [X] See user names (should be visible publicly)
- [X] NO action buttons visible (no cancel, check-in, etc.)
- [X] Try accessing other pages → should redirect to login

### Fridge List Page (`/schedule/fridges/`)

- [X] View fridge list without login
- [X] See machine names
- [X] See temperature readings (if available)
- [X] See online/offline status
- [X] NO edit/delete buttons visible

---

## 2. REGISTRATION & LOGIN FLOW

### Registration (`/register/`)

**Test Valid Registration:**
- [TODO] CHANGE TEXT TO SLACK INFORMATION, ALLOW SPACES IN USERNAME IS THERE A REASON WHY THEY AREN'T ALLOWED RN?
- [X] Fill in all fields correctly
  - Username: `test_newuser`
  - Email: `test@example.com`
  - Password: Strong password
  - First/Last Name
  - Security Question: Select from dropdown
  - Security Answer: Provide answer
- [X] Submit form
- [X] See success message: "Account created successfully! Your account is pending approval..."
- [X] Redirected to login page
- [X] Try logging in immediately → should see "pending approval" message
- [TODO] NOTIFY WHEN APPROVED!

**Test Invalid Registration:**
- [X] Try duplicate username → see error
- [X] Try weak password → see validation error
- [X] Try mismatched passwords → see error
- [X] Leave required fields blank → see validation errors
- [X] Try invalid email format → see error

### Login (`/login/`)

**Test Approved User Login:**
- [X] Enter valid credentials (test_user1)
- [TODO] Check "Remember Me" checkbox → session should last 1 year MIGHT COMMENT THIS OUT IT FEELS WEIRD
- [TODO] Don't check "Remember Me" → session should last 7 days GOOD DEFAULT AND THEY DONT HAVE TO DO ANYTHING
- [X] Successfully login → redirect to home page YES OR ADMIN PAGE
- [X] See username in top right corner
- [X] See "Logout" option

**Test Unapproved User Login:**
- [X] Login as `test_unapproved`
- [X] See "pending approval" message
- [TODO] Redirected back to login page WELL THEY CAN SEE WHAT TABS EXIST BUT THEY CAN'T ACCESS ANYTHING. I'M OK WITH THAT AS A FEATURE. LIKE A TASTE OF WHAT THEY'RE MISSING OUT ON.
- [X] Cannot access any authenticated pages
- [TODO] Fix bug: WHEN USER IS UNAPPROVED AND SOMEONE ELSE SIGNS IN FROM THERE, THE LOGIN PAGE IS STILL OF THAT OTHER USER SO IT SENDS THE YOU'RE NOT APPROVED MESSAGE, SO I THINK I NEED TO CHANGE HOW THE REDIRECT TO LOGIN WORKS SO THAT UNAPPROVED BASICALLY SAYS THE MESSAGE BUT LOGS THEM OUT AND BRINGS THEM BACK TO THE LOGIN WITH NOTHING ELSE VISIBLE.

**Test Invalid Login:**
- [X] Wrong password → see "invalid credentials" error
- [X] Wrong username → see "invalid credentials" error
- [X] Blank fields → see validation errors

**Test "Remember Me" Feature:**
- [X] Login WITH checkbox checked
- [X] Close browser completely
- [X] Reopen and visit site
- [X] Should still be logged in (1 year session)
- [X] Logout, login WITHOUT checkbox
- [X] Session should expire after 7 days (hard to test, check cookie expiry)

### Password Reset Flow (`/forgot-password/`)

- [X] Click "Forgot your password?" on login page
- [X] Enter username: `test_user1`
- [X] Submit → redirected to security question page
- [X] See user's security question displayed
- [X] Enter correct answer → redirected to password reset page
- [X] Enter new password (twice, matching)
- [X] Submit → see success message
- [X] Redirected to login
- [X] Login with NEW password → should work
- [X] Try login with OLD password → should fail

**Test Wrong Security Answer:**
- [X] Go through forgot password flow
- [X] Enter WRONG security answer
- [X] See error message
- [X] Should stay on security question page

### Username Recovery (`/recover-username/`)

- [X] Click "Forgot your username?" on login page
- [X] Enter email address: `test@example.com`
- [X] Submit
- [X] See username displayed on page
- [X] Try invalid email → see error message
- [TODO] FIX THE CASE OF MULTIPLE USERNAMES FOR ONE EMAIL ACCOUNT, RN IT 500 SERVER ERRORS WHICH IS FAIR.

---

## 3. REGULAR USER - NAVIGATION & PROFILE

### Navigation Bar (All Pages)

- [X] See username in top right
- [X] Hover/click username → see dropdown menu
- [X] Dropdown shows:
  - [X] "My Queue" link
  - [X] "Submit Queue Entry" link
  - [X] "Profile" link
  - [X] "Check In/Out" link (if has active jobs)
  - [X] "Notifications" link
  - [X] "Archive" link
  - [X] "Logout" link
- [X] NO admin links visible for regular users
- [X] All links navigate to correct pages

### User Profile Page (`/profile/`)

**Profile Information Tab:**
- [X] See current profile information displayed
- [TODO] Edit First Name → save → see success message NEED TO MAKE EDITABLE
- [TODO] Edit Last Name → save → see success message NEED TO BAKE EDITABLE
- [WouldWork] Changes reflected on page after refresh
- [X] Try blank required fields → see validation error
- [TODO] Make the slack member ID instructions easier, and make it A PART OF REGISTRATION THAT ISN'T REQUIRED.
**Notification Preferences Tab:**
- [X] See list of notification types
- [X] Toggle "Queue Position: On Deck" → save → see success
- [X] Toggle "Queue Position: Ready for Check-In" → save (should NOT disable - critical)
- [X] Toggle "Checkout Reminder" → save (should NOT disable - critical)
- [X] Toggle other notifications → save → verify saved
- [X] Refresh page → verify checkboxes reflect saved state
- [X] See "Followed Presets" section
- [X] See list of followed presets (if any)

**Security:**
- [X] Decide to delete changing 
- [TODO] Add a little line in the Profile Information that if you need to change your security question, username, email, or name, contact an administrator.
- [TODO] Make staff capable of changing ALL user information, including security question

---

## 4. QUEUE MANAGEMENT - REGULAR USER

### Submit Queue Entry (`/schedule/submit/`)

**Test Basic Submission:**
- [X] See form with all fields
- [NotAThingButThanks...ItAssignsBasedOnTheAssignmentAlgorithm] Select machine from dropdown
- [X] Enter job title: "Test Measurement 1"
- [X] Enter description/notes
- [TODO] Enter estimated duration: 2 hours DECIDE IF YOU WANT THIS
- [X] Select priority: Normal
- [X] Submit form
- [X] See success message
- [X] Redirected to "My Queue" page <-- Actually want them to stay on this page
- [X] See new entry in "My Upcoming Jobs" section

**Test Rush Job Request:**
- [X] Fill in form as above
- [X] Check "Request Rush Job" checkbox
- [X] Enter rush justification: "Urgent deadline tomorrow"
- [X] Submit
- [X] See message about pending admin approval
- [X] Entry should show "Rush (Pending)" status
- [X] Admin should see notification about rush request

**Test Preset Loading:**
- [X] Click "Load Preset" dropdown
- [X] Select existing preset
- [X] Verify form fields auto-fill with preset values
- [X] Modify one field
- [X] Submit
- [X] Verify entry uses modified values

**Test Preset Creation:**
- [X] Fill in form with specific values
- [X] Click "Save as Preset"
- [X] Enter preset name: "My Test Preset"
- [X] Choose visibility: "Private"
- [X] Submit
- [X] See success message
- [X] Refresh page → new preset appears in dropdown
- [X] Load preset → verify values match

**Test Following Presets:**
- [X] Load a preset created by ANOTHER user (if available)
- [X] Click "Follow This Preset" button (if visible)
- [X] See success message
- [X] Go to Profile → Notification Preferences
- [X] See preset in "Followed Presets" section
- [X] Unfollow from profile → verify removed

**Test Validation Errors:**
- [X] Submit form with missing machine → see error
- [X] Submit with missing title → see error
- [X] Submit with negative duration → see error
- [X] Submit with duration > 24 hours → see warning/error
- [X] Submit with missing justification for rush job → see error

### My Queue Page (`/schedule/my-queue/`)

**View My Queue:**
- [X] See "My Upcoming Jobs" section
- [X] See entries in order (rush first, then order number)
- [X] Each entry shows:
  - [X] Machine assignment
  - [X] Title
  - [X] Status (Pending, Ready, Running)
  - [X] Position in queue
  - [X] Estimated duration
  - [X] Rush indicator (if applicable)
- [X] See "My Completed Jobs" section (last 10)
- [X] See completed entries with completion dates

**Cancel Queue Entry:**
- [X] Find a PENDING entry
- [X] Click "Cancel" button
- [X] See confirmation dialog
- [X] Confirm cancellation
- [X] Entry disappears from list
- [X] See success message
- [X] Verify entry is gone after page refresh

**Test Cannot Cancel Running Entry:**
- [X] Try to cancel entry with status "Running"
- [X] Should NOT see cancel button (or see error if attempted)
- [X] Running entries can only be checked out, not cancelled

---

## 5. CHECK-IN/CHECK-OUT FLOW

### Check-In Process

**From My Queue Page:**
- [X] Find entry with status "Ready for Check-In"
- [X] Click "Check In" button
- [X] See confirmation dialog
- [X] Confirm check-in
- [X] Entry status changes to "Running"
- [X] See "Started At" timestamp
- [X] "Check In" button disappears
- [X] "Check Out" button appears
- [X] Estimated completion time displayed

**From Check In/Out Page (`/schedule/check-in-check-out/`):**
- [X] Visit check-in page
- [X] See "Ready to Check In" section
- [X] See entry listed
- [X] Click "Check In" button
- [X] See confirmation
- [X] Entry moves to "Currently Running" section

**Test Reminder Scheduling:**
- [X] After checking in, verify reminder is scheduled
- [X] Note the estimated completion time
- [Worked] (Hard to test immediately - requires waiting for reminder due time) I THINK I HAVE A CRYOCORE RUNNING RIGHT NOW TO CHECK THAT?? HAD TO CHANGE THE CODE A BIT. The code is still mad about something, when API is unreachable sometimes randomly, but it stays up, so eh. Ah, it has 40 minutes left.

### Check-Out Process

**From My Queue Page:**
- [TODO] SHOULD THERE BE AN UNDO CHECK-IN? I FEEL LIKE THAT'S GONNA MAKE IT DIFFICULT...
- [X] Find entry with status "Running"
- [X] Click "Check Out" button
- [X] See form with optional fields:
  - [X] Actual duration (auto-filled)
  - [X] Notes/results
  - [X] Option to save to archive <-- automatic
- [X] Fill in results/notes
- [X] Check "Save to Archive" if desired
- [X] Submit
- [X] Entry status changes to "Completed"
- [X] See "Completed At" timestamp
- [X] Entry moves to "Completed" section
- [X] If archived, see success message with archive link

**From Check In/Out Page:**
- [X] See "Currently Running" section
- [X] Find running entry
- [X] Click "Check Out" button
- [X] Fill in checkout form
- [X] Submit
- [X] Entry disappears from "Running" section
- [X] Moves to "Recent Completions" (if shown)

**Test Early/Late Checkout:** huh? [TODO]
- [ ] Check in to a job (estimated 2 hours)
- [ ] Check out after 30 minutes (early)
- [ ] Verify actual duration is calculated correctly (~0.5 hours)
- [ ] Check in to another job (estimated 1 hour)
- [ ] Wait longer than estimated (hard to test)
- [ ] Check out late
- [ ] Verify actual duration is calculated correctly

---

## 6. ARCHIVE MANAGEMENT - REGULAR USER

### View Archives (`/schedule/archive/`)
- [TODO] REMOVE THE ACTIONS TAB.
- [X] Visit archive page
- [X] See list of archived measurements
- [X] Filter by machine → dropdown filters list
- [X] Search by title → results filter correctly
- [X] See columns: Machine, Date, Title, Notes, Actions
- [TODO] Pagination works (if > 20 entries) NO PAGINATION MADE NOW
- [TODO] Remove the Day: Filtration. It's causing a bug with all years

### Save from Queue Entry

- [X] During check-out, enable "Save to Archive"
- [X] Fill in optional notes
- [X] Submit checkout
- [X] Go to archive page
- [X] Verify entry was created with:
  - [X] Correct machine
  - [X] Correct date (check-in date)
  - [X] Queue entry title
  - [X] Any notes added

### Export My Measurements

- [X] Click "Export My Measurements" button
- [X] See CSV file download
- [X] Open CSV in spreadsheet app
- [X] Verify contains:
  - [X] All YOUR archived measurements (not others')
  - [X] Correct columns: ID, Machine, Date, Title, Notes, Archived At
  - [X] Data is accurate

### Bulk Delete Archives

**Staff Only - Skip if Regular User**

### Delete Single Archive Entry

- [X] Find an archive entry YOU created
- [X] Click "Delete" button
- [X] See confirmation dialog
- [X] Confirm deletion
- [X] Entry disappears from list
- [X] See success message
- [X] Try to delete entry created by ANOTHER user
- [X] Should NOT see delete button (or get error)
- [TODO] PRIVATE PRESET DELETE BUTTONS AREN'T THANOS DIALOG. PUBLIC PRESET DELETE BUTTONS ARE! staff only

### Download Archive Files

- [X] Find entry with uploaded file
- [X] Click "Download" link
- [X] File downloads correctly
- [X] File is the correct file (not corrupted)
- [X] Verify filename matches original upload
- [TODO] EXPORT ALL MEASUREMENT BUTTON FOR ARCHIVE -- all users
---

## 7. PRESET MANAGEMENT - REGULAR USER

### View Preset (`/schedule/preset/view/<id>/`)

- [X] Navigate to preset view (from submit page "View" link)
- [X] See preset details:
  - [X] Name
  - [X] Creator
  - [X] Visibility (Private/Lab/Public)
  - [X] Machine
  - [X] Estimated duration
  - [X] Description/notes
  - [X] Fields (if any custom fields)
- [X] See "Use This Preset" button → redirects to submit page with preset loaded

### Create Preset (from Submit Page)

- [X] Fill in queue submission form
- [X] Click "Save as Preset" button
- [X] See preset creation modal
- [X] Enter name: "New Test Preset"
- [X] Select visibility: "Lab Members"
- [X] Submit
- [X] See success message
- [X] Preset appears in dropdown on submit page
- [X] Verify preset is saved correctly

### Edit Preset (`/schedule/preset/edit/<id>/`)

- [X] From submit page, select YOUR preset
- [X] Click "Edit Preset" button
- [X] See preset edit form
- [X] Change preset name: "Updated Preset Name"
- [X] Change visibility: "Public"
- [X] Modify default duration
- [X] Submit
- [X] See success message
- [X] Reload submit page → verify changes reflected
- [X] Try to edit ANOTHER user's preset
- [X] Should get permission denied error (unless preset is shared and editable)

### Copy Preset (`/schedule/preset/copy/<id>/`)

- [X] Select ANY preset (yours or others')
- [X] Click "Copy Preset" button
- [X] See copy form with preset values pre-filled
- [X] Change name: "Copied from X"
- [X] Change visibility if desired
- [X] Submit
- [X] See success message
- [X] New preset appears in YOUR preset list
- [X] Verify it's a separate copy (editing it doesn't affect original)

### Delete Preset

- [X] Select YOUR preset from dropdown
- [X] Click "Delete Preset" button
- [TODO] See confirmation dialog (possibly Thanos modal if implemented) NEED TO MAKE CUSTOM UI THANOS FOR STAFF AND NORMAL FOR NORMAL
- [TODO] MAKE CUSTOM OK DIALOG FOR IF THE PRESET YOU WERE VIEWING WAS DELETED BY ANOTHER USER
- [X] Confirm deletion
- [X] Preset disappears from dropdown
- [X] See success message
- [X] Try to delete preset you DON'T own
- [X] Should not see delete button or get permission error

### Follow/Unfollow Presets

**Follow Preset:**
- [X] Load a preset created by ANOTHER user
- [X] Click "Follow This Preset" button
- [X] See success message
- [X] Go to Profile → Notification Preferences
- [X] See preset listed in "Followed Presets"
- [TODO] When preset is updated, you should get notification (test later) NOT WORKING

**Unfollow Preset:**
- [X] From Profile page, find followed preset
- [X] Click "Unfollow" button
- [X] Preset removed from list
- [X] No longer receive updates about this preset
- [TODO] MAKE UNFOLLOW A THANOS SNAP DIALOG for admins

---

## 8. NOTIFICATIONS - REGULAR USER

### View Notifications (`/schedule/notifications/`)
- [ ] IF THEY'RE NOT ON SLACK, USE EMAIL
- [ ] DON'T DOUBLE NOTIFICATION? MAYBE OK TO LEAVE, BUT PROBABLY SHOULD LEAVE IT AS 
- [ ] NEED THE POSITION #1 NOTIFICATION TO REFLECT THE MACHINE STATUS (If it's not running and is available, send it, otherwise, check every hour until it's not running and is available (as ooposed to disabled by admin (which stops you from checking in)), like if there's no running measurement in it)
- [ ] Visit notifications page
- [ ] See notification list sorted by date (newest first)
- [ ] Unread notifications highlighted/bolded
- [ ] Each notification shows:
  - [ ] Icon (based on type)
  - [ ] Title
  - [ ] Message
  - [ ] Timestamp
  - [ ] Read/Unread status
- [ ] Click notification title → marks as read
- [ ] If notification has link → clicking navigates to relevant page

### Mark Notifications as Read

- [ ] Find unread notification
- [ ] Click "Mark as Read" button
- [ ] Notification styling changes (no longer bold)
- [ ] Badge count decreases (if badge exists)
- [ ] Click "Mark All as Read" → all notifications marked
- [ ] Badge count goes to 0

### Dismiss Notifications

- [ ] Click "Dismiss" button on notification
- [ ] Notification disappears from list
- [ ] Still accessible in database (not deleted, just hidden)

### Clear Read Notifications

- [ ] Click "Clear Read Notifications" button
- [ ] See confirmation
- [ ] All read notifications disappear
- [ ] Unread notifications remain

### Notification Types to Test

**Create test scenarios to trigger each notification type:**

**Queue Position: On Deck**
- [ ] Have admin move YOUR entry to position #2 or #3
- [ ] Check notifications → should see "Your job is on deck" notification
- [ ] Verify notification has link to queue page

**Queue Position: Ready for Check-In**
- [ ] Have entry reach position #1
- [ ] Check notifications → should see "Ready to check in" notification
- [ ] Verify notification has link to check-in page
- [ ] Notification marked as CRITICAL

**Checkout Reminder**
- [ ] Check in to a job with 1 hour estimated duration
- [ ] Wait until estimated completion time (hard to test)
- [ ] OR have admin manually trigger reminder check
- [ ] Check notifications → should see "Time to check out" reminder
- [ ] Notification marked as CRITICAL
- [ ] Includes link to checkout page

**Rush Job Approved**
- [ ] Submit rush job request
- [ ] Have admin approve it
- [ ] Check notifications → should see "Rush job approved" notification
- [ ] Entry should now show as "Rush" in queue

**Rush Job Rejected**
- [ ] Submit rush job request
- [ ] Have admin reject it
- [ ] Check notifications → should see "Rush job rejected" notification
- [ ] Message includes admin's rejection reason

**Queue Entry Cancelled by Admin**
- [ ] Have admin cancel YOUR queue entry
- [ ] Check notifications → should see cancellation notification
- [ ] Message includes admin's reason

**Preset Followed - Updates**
- [ ] Follow a preset created by another user
- [ ] Have that user update the preset
- [ ] Check notifications → should see "Preset updated" notification

**Admin Actions (New User, etc.)**
- [ ] These are admin-only, test in admin section

### Notification Settings Test

- [ ] Go to Profile → Notification Preferences
- [ ] Disable "On Deck" notifications
- [ ] Trigger "on deck" event (move to position 2-3)
- [ ] Verify NO notification received
- [ ] Re-enable setting
- [ ] Trigger event again → should receive notification
- [ ] Try to disable CRITICAL notifications (Ready for Check-In, Checkout Reminder)
- [ ] Should remain enabled (force-enabled in backend)

---

## 9. SLACK INTEGRATION TESTING (Optional)

**Skip this section if SLACK_BOT_TOKEN is not configured**

### Setup

- [X] Verify SLACK_BOT_TOKEN is set in Render environment
- [X] Verify YOUR user has Slack User ID configured in profile
- [X] Verify Slack bot is installed in workspace

### Test Slack Notifications

**For each notification type above, verify Slack DM is received:**

**Ready for Check-In (Slack):**
- [X] Trigger "ready for check-in" event
- [X] Check Slack DMs from bot
- [X] Should receive message about job ready
- [X] Message includes one-time login link
- [X] Click link → should auto-login and redirect to check-in page

**Checkout Reminder (Slack):**
- [X] Trigger checkout reminder
- [X] Check Slack DMs
- [X] Should receive reminder message
- [X] Message includes login link to checkout page

**Rush Job Approved/Rejected (Slack):**
- [X] Trigger rush job decision
- [X] Check Slack DMs
- [X] Should receive notification with decision

**One-Time Login Token:**
- [X] Receive Slack notification with link
- [X] Click link → should auto-login
- [X] Should redirect to intended page (check-in, queue, etc.)
- [X] Token should work multiple times (not consumed on first use)
- [X] After 24 hours, token should expire
- [X] Expired token shows error message
- [TODO] Chnage expired token message to be about how it's been more than 24 hours, the link has expired.
**Test Wrong User Token Login:**
- [X] Get notification link meant for test_user1
- [X] Log in as test_user2
- [X] Click test_user1's notification link
- [X] Should be logged out automatically
- [X] Should see message: "This link is for test_user1..."
- [X] Should be prompted to login as correct user

---

## 10. ADMIN DASHBOARD - STAFF USERS ONLY

### Access Admin Dashboard

**Login as test_admin (staff user):**
- [X] See "Admin Dashboard" link in navigation dropdown
- [X] Click → navigate to `/schedule/admin-dashboard/`
- [X] See dashboard with widgets:
  - [X] Total Users
  - [X] Pending Approvals
  - [X] Active Queue Entries
  - [X] Total Machines
  - [X] Rush Job Requests
- [X] See navigation cards for:
  - [X] User Management
  - [X] Queue Management
  - [X] Machine Management
  - [X] Preset Management
  - [X] Database Management
  - [X] Storage Stats
  - [X] Rush Job Review

**Test Regular User Access:**
- [X] Login as test_user1 (non-staff)
- [X] Try accessing `/schedule/admin-dashboard/` directly
- [X] Should get "Permission Denied" error or redirect

---

## 11. USER MANAGEMENT - ADMIN

### View Users (`/schedule/admin-users/`)

- [X] See list of all users
- [X] Each user shows:
  - [X] Username
  - [X] Email
  - [X] Name
  - [X] Approval status
  - [X] Staff status
  - [X] Date joined
  - [X] Actions (Approve/Reject/Delete/Promote/Demote)
- [TODO] Make Approve/Unapprove/Delete all the same size (Unapprove size)
- [X] See separate sections:
  - [X] Pending Approvals (highlighted)
  - [X] Approved Users
  - [X] Rejected Users
- [TODO] Alphabetize by username PLEASE IT'S KILLING ME

### Approve User

- [X] Find test_unapproved in pending list
- [X] Click "Approve" button
- [X] See confirmation
- [X] User moves to "Approved Users" section
- [TODO] User receives notification (check in their account)
- [X] User can now login and access site

### Reject User

- [X] Create new test account that needs approval
- [X] In admin panel, click "Reject" button [TODO] NOTE THERE IS NO REJECT BUTTON, just DELETE
- [X] Enter rejection reason: "Test rejection"
- [X] Submit
- [X] User moves to "Rejected Users" section
- [X] User receives notification with reason
- [X] User still cannot login
- [TODO] MAKE REJECTED OPTION for button and Status
- [TODO] In MANAGE USERS, MAKE UNAPPROVE USERS THE TOP SECTION, THEN ACTIVE USERS, THEN REJECTED USERS
- [TODO] REJECTED USERS CAN BE APPROVED OR DELETED.
- [TODO] Defend against ddos attack how?
### Delete User

- [X] Find user you want to delete (NOT yourself)
- [X] Click "Delete" button
- [X] See confirmation dialog (warning about data deletion)
- [X] Confirm deletion
- [X] User removed from list
- [X] User's data (queue entries, archives) should be deleted or orphaned
- [X] User cannot login anymore

### Promote to Staff

- [X] Find approved regular user (test_user1)
- [X] Click "Promote to Staff" button
- [X] See confirmation
- [X] User now shows as "Staff: Yes"
- [TODO] User receives notification about promotion or demotion
- [X] Login as that user → should see admin links now

### Demote from Staff

- [X] Find staff user (not yourself, not superuser)
- [X] Click "Demote from Staff" button
- [X] See confirmation
- [X] User no longer shows as staff
- [X] Login as that user → admin links disappear

### Test Cannot Demote Self

- [X] Try to demote your own account
- [X] Should see error message
- [X] Action should be blocked
- [TODO] Thus, REMOVE PENDING USERS PAGE AND FIX THE DIRECT FROM THE LINK OF NOTIFICATION TO ADMINS FOR PENDING USERS NOTIF.
---

## 12. MACHINE MANAGEMENT - ADMIN

### View Machines (`/schedule/admin-machines/`)

- [X] See list of all machines
- [ ] Each machine shows:
  - [X] Name
  - [?] Slug (URL identifier)
  - [X] Description
  - [X] Status (Online/Offline/Maintenance)
  - [X] Temperature (if available)
  - [X] Last updated
  - [X] Actions (Edit/Delete)

### Add Machine

- [X] Click "Add New Machine" button
- [X] Fill in form:
  - [X] Name: "Test Machine 4"
  - [X] Slug: "test-machine-4" (auto-generated or manual)
  - [X] Description: "Test equipment for testing"
  - [X] Status: "Online"
- [X] Submit
- [X] See success message
- [X] Machine appears in list
- [X] Machine appears in queue submission dropdown
- [TODO] CHANGE TEXT FROM EDIT MACHINE TO EDIT/DELETE
### Edit Machine

- [X] Click "Edit" on existing machine
- [X] Change name: "Updated Test Machine"
- [X] Change status: "Maintenance"
- [X] Change description
- [X] Submit
- [X] See success message
- [X] Changes reflected in machine list
- [X] Changes reflected in public pages (queue, fridges)
- [TODO] FIX BORDER/FITTING OF THE CONTENT FOR admin-queue page. Rn if page small it extends beyond the blue border instead of just making the things scrollable within the blue border, you know?
### Delete Machine

**Test Cannot Delete with Active Queue Entries:**
- [X] Find machine with pending/running queue entries
- [X] Click "Delete" button
- [X] Should see error: "Cannot delete machine with active queue entries"
- [X] Machine remains in list

**Test Successful Deletion:**
- [X] Find machine with NO queue entries
- [X] Click "Delete" button
- [X] See confirmation dialog
- [X] Confirm deletion
- [X] Machine removed from list
- [X] Machine no longer appears in dropdowns
- [TODO] QUEUE ENTRIES DETECTED --> IT HAS N active QUEUE ENTRIES, ARE YOU SURE YOU WOULD LIKE TO DELETE MACHINE X? YES, RESOTRE BALANCE or NO, SPARE THEM ALL. If none active, just do it. Even if archived. The database isn't set up to handle a new machine ,for some reason. Like the measurement for new machine finished, but it doesn't show up in archive, even though it is completed.

### Temperature Updates (If temperature gateway configured)

- [X] Check machine temperature display
- [X] If temperature gateway is running:
  - [X] See actual temperature values
  - [X] See last updated timestamp
  - [X] Temperature updates every 5 minutes
- [X] If no temperature gateway:
  - [X] Temperature shows as "None" or "N/A"
- [TODO] FIX UP THE REST OF THE TEMPERATURE GATEWAY CODE FOR THE 3 OTHER MACHINES
---

## 13. QUEUE MANAGEMENT - ADMIN

### View Admin Queue (`/schedule/admin-queue/`)

- [X] See comprehensive queue view
- [X] Sections:
  - [X] All Pending Entries (ordered)
  - [X] Running Entries
  - [X] Recently Completed
- [X] Each entry shows:
  - [X] Position number
  - [X] User
  - [X] Machine
  - [X] Title
  - [X] Status
  - [X] Rush indicator
  - [X] Estimated duration
  - [X] Actions

### Edit Queue Entry

- [TODO] Click "Edit" on any entry, even running ones? That interaction is scary.
- [X] See edit form with all fields
- [TODO] FIX THE CHECKBOX DISPLAY ON THE EDIT FORM
- [X] Change machine assignment
- [X] Change estimated duration
- [X] Change notes
- [X] Submit
- [X] See success message
- [X] Changes reflected in queue
- [X] User receives notification about changes
- [TODO] Figure out what can be changed about a running entry: Name, notes, etc.
### Cancel Queue Entry (Admin)
- [TODO] Don't notify about position changes when it's from a delete of one behind it in the queue
- [X] Click "Cancel" on any entry
- [ ] Enter cancellation reason: "Admin test cancellation"
- [ ] Submit
- [ ] Entry removed from queue
- [ ] User receives notification with reason
- [TODO] Details if logged in, otherwise just name, have a field for details with description: GIve a detailed description as to what meassurements you're needin to do. Don't pull up user.
### Move Entry Up in Queue

- [X] Find entry at position #5 or higher
- [X] Click "Move Up" button
- [X] Entry moves to position #4
- [X] Order numbers adjust for other entries
- [X] Click repeatedly → entry continues moving up
- [X] Cannot move above position #1

### Move Entry Down in Queue

- [X] Find entry near top of queue
- [X] Click "Move Down" button
- [X] Entry moves down one position
- [X] Other entries adjust
- [X] Click repeatedly → entry continues moving down

### Queue Next (Jump to Position #1)

- [X] Find entry at position #7
- [X] Click "Queue Next" button
- [X] See confirmation
- [X] Entry jumps to position #1
- [X] All other entries shift down
- [X] User receives "Ready for Check-In" notification

### Reassign Machine

- [ ] Click "Reassign Machine" on entry
- [ ] See dropdown with all machines
- [ ] Select different machine
- [ ] Submit
- [ ] Machine assignment updated
- [ ] Entry position may change based on new machine's queue
- [ ] User receives notification about change

### Admin Check-In (For User)

- [X] Find entry at position #1 (ready to check in)
- [X] Click "Check In" button
- [X] Entry status changes to "Running"
- [X] Started timestamp recorded
- [X] User receives notification
- [X] Reminder scheduled

### Admin Check-Out (For User)

- [X] Find running entry
- [X] Click "Check Out" button
- [X] Fill in completion form (optional notes)
- [X] Submit
- [X] Entry status changes to "Completed"
- [X] Completed timestamp recorded
- [X] User receives notification
- [X] Next entry in queue becomes "Ready"

---

## 14. RUSH JOB REVIEW - ADMIN

### View Rush Job Requests (`/schedule/admin-rush-jobs/`)
- [TODO] Send the correct notification when moved into first by admin: Machine ready vs just on deck
- [TODO] REMOVE MAX TEMP, JUST COMMENT IT OUT from every form, IT"S CONFUSING
- [X] See list of pending rush job requests
- [X] Each request shows:
  - [X] User
  - [X] Machine
  - [X] Title
  - [X] Justification
  - [X] Requested date
  - [X] Actions (Approve/Reject)
- [X] If no requests, see "No pending rush job requests" message

### Approve Rush Job

- [X] Have test_user1 submit rush job request
- [X] In admin panel, see request appear
- [X] Click "Approve" button
- [X] Entry marked as "Rush"
- [X] Entry moves to front of queue (position #1 or near top)
- [X] User receives "Rush job approved" notification
- [X] Request disappears from pending list

### Reject Rush Job

- [X] Have test_user2 submit rush job request
- [X] Click "Reject" button
- [TODO] Enter rejection reason: "Insufficient justification"
- [X] Submit
- [X] Entry remains in queue at regular position (not rushed)
- [TODO] User receives "Rush job rejected" notification with reason
- [X] Request disappears from pending list

---

## 15. PRESET MANAGEMENT - ADMIN

### View All Presets (`/schedule/admin-presets/`)

- [X] See list of ALL presets (all users, all visibility levels)
- [X] Each preset shows:
  - [X] Name
  - [X] Creator
  - [X] Visibility
  - [X] Machine
  - [X] Created date
  - [X] Actions (View/Edit/Delete)
- [X] ORDER by visibility: Private/Lab/Public
- [X] ORDER by creator

### Admin Edit Any PUBLIC Preset

- [X] Click "Edit" on preset created by ANOTHER user
- [X] See edit form
- [X] Make changes
- [X] Submit
- [X] Changes saved
- [X] Creator receives notification about admin edit

### Admin Delete Any PUBLIC Preset

- [X] Click "Delete" on any preset
- [X] See confirmation (Thanos modal if implemented)
- [X] Confirm deletion
- [X] Preset removed
- [X] Users following this preset receive notification

---

## 16. DATABASE MANAGEMENT - ADMIN

### View Storage Stats (`/schedule/admin/storage-stats/`)

- [X] See database size information
- [X] See storage usage percentage
- [X] See breakdown by table:
  - [X] Queue Entries
  - [X] Archived Measurements
  - [X] Users
  - [X] Notifications
  - [X] Sessions
- [X] See total size in MB
- [X] See warning if over threshold (>80% of 3GB for Neon)

### Export Full Database

- [X] Click "Export Entire Database" button
- [X] See download start immediately (or after short processing)
- [X] Download completes with JSON file
- [X] Filename format: `database_backup_YYYY-MM-DD_HH-MM-SS.json`
- [X] File size should be reasonable (check it's not empty)
- [X] Open file → verify it's valid JSON
- [X] Should contain all tables: users, queue entries, machines, etc.

### Export Archive Only

- [X] Click "Export Archive Only" button
- [X] Download JSON file
- [X] Open file → verify it contains only archived measurements
- [X] Should NOT include users, queue entries, etc.

### Import/Restore Database

**Test Replace Mode:**
- [X] Click "Import/Restore Database" button
- [X] Select mode: "Replace (Delete existing data)"
- [X] Upload backup JSON file (from previous export)
- [X] See Thanos modal warning
- [X] Type "CONFIRM RESTORE" in text box
- [X] Submit
- [X] See processing message
- [X] See success message after completion
- [X] Verify data was restored:
  - [X] Check queue entries match backup
  - [X] Check users match backup
  - [X] Check machines match backup
  - [X] Current data was wiped and replaced

**Test Merge Mode:**
- [X] Make note of current database state (count entries)
- [X] Upload backup JSON with DIFFERENT data
- [X] Select mode: "Merge (Keep existing data)"
- [X] See Thanos modal
- [X] Type "CONFIRM RESTORE"
- [X] Submit
- [X] See success message
- [X] Verify data was merged:
  - [X] Old entries still exist
  - [X] New entries from backup added
  - [X] Duplicate entries handled appropriately
  - [X] Entry count increased

**Test Validation Errors:**
- [X] Try to upload invalid JSON file → see error
- [X] Try to upload JSON with wrong structure → see error
- [X] Try without typing "CONFIRM RESTORE" → submission blocked

### Clear Archive with Backup

- [X] Click "Clear Archive with Backup" button
- [X] See confirmation
- [X] Download backup JSON starts
- [X] After download, archive data is cleared
- [X] Archive page shows 0 entries
- [X] Backup file contains all deleted archives
- [X] Other data (users, queue) unaffected

### Clear Archive (Without Backup) THERE IS NO OPTION FOR THAT.

- [X] Click "Clear Archive" button (dangerous action)
- [X] See strong warning message
- [X] See Thanos modal with text confirmation
- [X] Type confirmation text
- [X] Submit
- [X] All archived measurements deleted
- [X] Archive page shows 0 entries
- [X] NO backup file generated
- [X] Other data unaffected

---

## 17. RENDER USAGE STATS - ADMIN (Optional)

### View Render Usage (`/schedule/admin/render-usage/`)
NOT REAL DATA PROBABLY, JUST MATH
- [X] See usage statistics (if implemented)
- [X] See request count for current month
- [X] See estimated uptime hours
- [X] See percentage of free tier limit used
- [X] See days remaining in month
- [X] Color coding: green (<80%), yellow (80-95%), red (>95%)

---

## 18. EDGE CASES & ERROR HANDLING

### Session Expiration

**Test 7-Day Session (no "Remember Me"):**
- [ ] Login without "Remember Me" checkbox
- [ ] Come back 7+ days later (hard to test - can manually expire cookie)
- [ ] Should be logged out
- [ ] Redirected to login page
- [ ] After login, redirected to intended page

**Test 1-Year Session ("Remember Me" checked):**
- [ ] Login WITH "Remember Me" checkbox
- [ ] Close browser, clear cache (but not cookies)
- [ ] Reopen site weeks later
- [ ] Should still be logged in

### Concurrent User Actions

**Test Race Conditions:**
- [ ] Open site in two browser tabs as same user
- [ ] Tab 1: Start editing queue entry
- [ ] Tab 2: Delete the same entry
- [ ] Tab 1: Try to save changes
- [ ] Should see error: "Entry no longer exists"
- [TODO] Allow delete but catch save if doesn't exist gracefully with a banner and a reload.

**Test Queue Position Updates:**
- [ ] Open queue page in two tabs
- [ ] Tab 1: Admin moves entry up
- [ ] Tab 2: Refresh → should see new position
- [ ] Both tabs should show consistent order
- [TODO] Queue admin reordering needs some love. Not sure how to fix it.

### Invalid URLs

- [X] Try accessing `/schedule/edit/9999999/` (non-existent entry)
- [X] Should see 404 error
- [X] Try accessing `/schedule/preset/view/9999/` (non-existent preset)
- [X] Should see 404 error
- [X] Try accessing deleted entry URL
- [X] Should see 404 or "Entry not found" message

### Permission Errors

**Regular User Accessing Admin Pages:**
- [X] Login as regular user
- [X] Try accessing `/schedule/admin-dashboard/` directly
- [X] Should see "Permission Denied" error or redirect to home
- [X] Try accessing `/schedule/admin-users/` directly
- [X] Should see error/redirect

**User Editing Other User's Data:**
- [ ] Login as test_user1
- [ ] Try to cancel test_user2's queue entry (if URL guessable)
- [ ] Should see "Permission Denied" error
- [ ] Try to edit test_user2's preset
- [ ] Should see error
- [TODO] WYM Try to cancel??? wym guessable?
### Database Connection Errors

**Simulate Connection Loss:**
- [ ] Stop Neon database (pause it)
- [ ] Try to access any page requiring DB
- [ ] Should see graceful error message (not raw traceback)
- [ ] Or site hangs with connection timeout
- [ ] Restart database
- [ ] Site should recover automatically

### Large Data Handling

**Test with Many Queue Entries:**
- [ ] Create 50+ queue entries
- [ ] Load admin queue page
- [ ] Page should load without timeout
- [ ] Pagination should work (if implemented)
- [ ] Moving entries should still work

**Test with Large Archive:**
- [ ] Have 100+ archived measurements
- [ ] Load archive page
- [ ] Pagination should work
- [ ] Export should complete without timeout
- [ ] File size should be reasonable (<10MB)

### File Upload Edge Cases

- [TODO] Allow spaces in username?

### Cross-Site Request Forgery (CSRF)

- [ ] All forms should have CSRF token
- [ ] Try submitting form without CSRF token (use browser dev tools)
- [ ] Should see "CSRF token missing" error
- [ ] Form submission should be rejected
- [TODO] Learn what this is
---

## 19. WEBSOCKET REAL-TIME UPDATES (Production Only)

**Note:** These only work on production (Render with Daphne), not local runserver

### Queue Updates

- [ ] Open queue page in two browsers (different users)
- [ ] Browser 1: Admin moves entry in queue
- [ ] Browser 2: Should see entry position update WITHOUT refresh
- [ ] Test with multiple simultaneous admins
- [TODO] Make the refresh not needed for ordering. Query the database in the websocket??? IDK
### Preset Updates

- [ ] Browser 1: User edits preset
- [ ] Browser 2: User following that preset
- [ ] Browser 2: Should see notification banner "Presets updated"
- [ ] Browser 2: Click "Refresh" in banner
- [ ] Preset dropdown updates with changes

### Machine Status Updates

- [ ] Temperature gateway updates machine temperature
- [ ] Fridge page should update temperature WITHOUT refresh
- [ ] Online/offline status should update in real-time

---

## 20. MOBILE RESPONSIVENESS

### Test on Mobile Device or Browser Dev Tools

**Navigation:**
- [X] Menu collapses to hamburger icon on small screens
- [X] Hamburger menu opens/closes correctly
- [X] All links accessible on mobile
- [ ] Dropdowns work on touch

**Forms:**
- [ ] Queue submission form usable on mobile
- [ ] All fields accessible
- [ ] Date/time pickers work on mobile browsers
- [ ] Submit buttons reachable

**Tables:**
- [ ] Queue table scrolls horizontally if needed
- [ ] Archive table readable on mobile
- [ ] Admin tables functional on tablets

**Buttons:**
- [ ] All buttons large enough to tap
- [ ] No overlapping click areas
- [ ] Confirmation dialogs display correctly

---
- [TODO] Remove schedule entries from db and endpoints
## 21. BROWSER COMPATIBILITY

Test on multiple browsers:

### Chrome/Chromium
- [ ] All features work
- [ ] No console errors
- [ ] WebSockets connect (in production)
- [ ] Forms submit correctly

### Firefox
- [ ] All features work
- [ ] Date pickers display correctly
- [ ] No console errors
- [ ] Everything renders properly

### Safari (macOS/iOS)
- [ ] Site loads correctly
- [ ] Forms work
- [ ] Date/time pickers use native controls
- [ ] No layout issues

### Edge
- [ ] Site functions correctly
- [ ] No compatibility issues
- [ ] All features accessible

---

## 22. PERFORMANCE TESTING

### Page Load Times

- [ ] Homepage loads in <2 seconds
- [ ] Queue page loads in <3 seconds (with 50+ entries)
- [ ] Admin dashboard loads in <3 seconds
- [ ] Archive page loads in <4 seconds (with pagination)

### Database Query Performance

- [ ] Queue list queries <1 second
- [ ] Archive search/filter <2 seconds
- [ ] Admin user list <1 second
- [ ] Export operations complete within timeout

### Concurrent Users

- [ ] 5 users accessing site simultaneously
- [ ] No slowdowns or errors
- [ ] Queue updates handle multiple admins
- [ ] No race conditions or data corruption

---

## 23. SECURITY TESTING

### Authentication

- [X] Cannot access authenticated pages without login
- [TODO] Session expires after inactivity (7 days for non-remember-me)
- [X] Logout completely clears session
- [X] Cannot reuse old session cookies after logout

### Authorization

- [X] Regular users cannot access admin pages
- [X] Users cannot modify other users' data
- [X] Staff-only features blocked for regular users
- [X] Superuser features blocked for non-superusers

### SQL Injection Prevention

- [TODO] Try entering `' OR '1'='1` in search fields
- [TODO] Should NOT cause SQL errors
- [TODO] Should NOT bypass authentication
- [TODO] Django ORM should parameterize queries

### XSS Prevention

- [TODO] Enter `<script>alert('XSS')</script>` in form fields
- [TODO] Should be escaped/sanitized when displayed
- [TODO] Should NOT execute as JavaScript
- [TODO] Check queue title, notes, preset names

### CSRF Protection

- [TODO] All forms include CSRF token
- [TODO] Cannot submit forms from external sites
- [TODO] CSRF token validated on submission

---

## 24. DATA INTEGRITY

### Cascading Deletes

**Delete User with Data:**
- [ ] Create user with queue entries and archives
- [ ] Delete user via admin panel
- [ ] Verify user's queue entries are handled (deleted or orphaned)
- [ ] Verify user's archives are handled appropriately
- [ ] No orphaned data in database

**Delete Machine with Data:** [TODO] Should have been done elsewhere.
- [ ] Try to delete machine with active queue entries
- [ ] Should be blocked with error
- [ ] Complete/cancel all entries for that machine
- [ ] Now deletion should succeed

### Data Validation

**Queue Entry Validation:**
- [ ] Cannot create entry with negative duration
- [ ] Cannot create entry without machine
- [ ] Cannot create entry without title
- [ ] Estimated duration must be reasonable (<100 hours)

**User Data Validation:**
- [X] Email must be valid format
- [X] Username must be unique
- [X] Password must meet complexity requirements
- [X] Required fields enforced

### Timestamps

- [X] Created timestamps set automatically
- [X] Updated timestamps change on edit
- [TODO] Timezone-aware timestamps stored correctly
- [TODO] Check that Times display in correct timezone for user

---

## 25. BACKUP & RECOVERY

### Test Database Export/Import Cycle

1. **Export Current Database:**
   - [X] Export full database
   - [X] Note counts: X users, Y queue entries, Z archives

2. **Make Changes:**
   - [TODO] Add 5 new queue entries
   - [TODO] Delete 2 users
   - [TODO] Create 3 new presets
Add/delete each
3. **Restore from Backup:**
   - [TODO] Import backup in "Replace" mode
   - [TODO] Verify counts match original (X users, Y entries, Z archives)
   - [TODO] Verify recent changes are gone (back to backup state)

4. **Test Merge Mode:**
   - [TODO] Make backup of current state
   - [TODO] Add new data
   - [TODO] Import backup in "Merge" mode
   - [TODO] Verify OLD data exists
   - [TODO] Verify NEW data also exists
   - [TODO] No duplicates created

---

## TESTING COMPLETION CHECKLIST

After completing all sections:

### Critical Features (Must Pass)
- [ ] User registration and login work
- [ ] Queue submission works
- [ ] Check-in/check-out flow works
- [ ] Admin can manage users
- [ ] Admin can manage queue
- [ ] Notifications are sent and received
- [ ] Data is saved correctly

### Important Features (Should Pass)
- [ ] Preset creation/editing works
- [ ] Archive management works
- [ ] Rush job workflow works
- [ ] Permission system works correctly
- [ ] Database export/import works
- [TODO] Add page somewheree for admins to edit the matchmaking algorithm (i.e. checkbox for if to enforce Optical Requirement if selected, prioritization order, etc.)
- [TODO] FIX Fridge Specifications what info it reveals, and Status message changing based on query. The Offline status is great, but I would live the Disconnected - Idle Connected - Measuring to show up under Status:
- [TODO] Fix how the title bar looks.
### Nice-to-Have Features (Test if time)
- [ ] WebSocket real-time updates (production only)
- [ ] Slack notifications (if configured)
- [ ] Mobile responsiveness
- [ ] Browser compatibility

### Known Issues Found
Document any bugs/issues discovered:

1. **[Bug Title]** - Description, Steps to Reproduce, Severity
2. **[Bug Title]** - Description, Steps to Reproduce, Severity
3. etc.

---

## FINAL SIGN-OFF

Testing completed by: _________________ Date: _________________

All critical features: ☐ PASS ☐ FAIL

System ready for production: ☐ YES ☐ NO

Notes:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

**END OF COMPREHENSIVE TESTING CHECKLIST**

*Version: 1.0*
*Last Updated: 2025-11-12*
