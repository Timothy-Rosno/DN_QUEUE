# Comprehensive Testing Checklist - Queue Management System

**Purpose:** Test every feature, page, and user interaction to identify bugs and verify functionality.

**Testing Approach:** Work through each section systematically, checking off items as you verify they work.

---

## Testing Setup

### Test User Accounts Needed

Create these accounts for testing:

- [ ] **Test Admin** - Username: `test_admin` - Staff status: YES
- [ ] **Test User 1** - Username: `test_user1` - Approved, not staff
- [ ] **Test User 2** - Username: `test_user2` - Approved, not staff
- [ ] **Test User 3** - Username: `test_unapproved` - NOT approved yet
- [ ] **Test User 4** - Username: `test_user_slack` - With Slack ID configured (if testing Slack)

### Test Data Setup

- [ ] At least 3 machines configured (different names, statuses)
- [ ] At least 5 queue entries in various states (pending, ready, running, completed)
- [ ] At least 3 presets created by different users
- [ ] Some archived measurements

---

## 1. GUEST/UNAUTHENTICATED USER TESTING

### Homepage (`/`)

- [ ] Visit homepage without being logged in
- [ ] See welcome message and description
- [ ] Click "View Public Queue" link → redirects to `/schedule/queue/`
- [ ] Click "View Lab Fridges" link → redirects to `/schedule/fridges/`
- [ ] Click "Login" button → redirects to login page
- [ ] Click "Register" button → redirects to registration page
- [ ] No admin links visible

### Public Queue Page (`/schedule/queue/`)

- [ ] View queue without login
- [ ] See all pending and running queue entries
- [ ] See machine assignments
- [ ] See estimated durations
- [ ] See user names (should be visible publicly)
- [ ] NO action buttons visible (no cancel, check-in, etc.)
- [ ] Try accessing other pages → should redirect to login

### Fridge List Page (`/schedule/fridges/`)

- [ ] View fridge list without login
- [ ] See machine names
- [ ] See temperature readings (if available)
- [ ] See online/offline status
- [ ] NO edit/delete buttons visible

---

## 2. REGISTRATION & LOGIN FLOW

### Registration (`/register/`)

**Test Valid Registration:**
- [ ] Fill in all fields correctly
  - Username: `test_newuser`
  - Email: `test@example.com`
  - Password: Strong password
  - First/Last Name
  - Security Question: Select from dropdown
  - Security Answer: Provide answer
- [ ] Submit form
- [ ] See success message: "Account created successfully! Your account is pending approval..."
- [ ] Redirected to login page
- [ ] Try logging in immediately → should see "pending approval" message

**Test Invalid Registration:**
- [ ] Try duplicate username → see error
- [ ] Try weak password → see validation error
- [ ] Try mismatched passwords → see error
- [ ] Leave required fields blank → see validation errors
- [ ] Try invalid email format → see error

### Login (`/login/`)

**Test Approved User Login:**
- [ ] Enter valid credentials (test_user1)
- [ ] Check "Remember Me" checkbox → session should last 1 year
- [ ] Don't check "Remember Me" → session should last 7 days
- [ ] Successfully login → redirect to home page
- [ ] See username in top right corner
- [ ] See "Logout" option

**Test Unapproved User Login:**
- [ ] Login as `test_unapproved`
- [ ] See "pending approval" message
- [ ] Redirected back to login page
- [ ] Cannot access any authenticated pages

**Test Invalid Login:**
- [ ] Wrong password → see "invalid credentials" error
- [ ] Wrong username → see "invalid credentials" error
- [ ] Blank fields → see validation errors

**Test "Remember Me" Feature:**
- [ ] Login WITH checkbox checked
- [ ] Close browser completely
- [ ] Reopen and visit site
- [ ] Should still be logged in (1 year session)
- [ ] Logout, login WITHOUT checkbox
- [ ] Session should expire after 7 days (hard to test, check cookie expiry)

### Password Reset Flow (`/forgot-password/`)

- [ ] Click "Forgot your password?" on login page
- [ ] Enter username: `test_user1`
- [ ] Submit → redirected to security question page
- [ ] See user's security question displayed
- [ ] Enter correct answer → redirected to password reset page
- [ ] Enter new password (twice, matching)
- [ ] Submit → see success message
- [ ] Redirected to login
- [ ] Login with NEW password → should work
- [ ] Try login with OLD password → should fail

**Test Wrong Security Answer:**
- [ ] Go through forgot password flow
- [ ] Enter WRONG security answer
- [ ] See error message
- [ ] Should stay on security question page

### Username Recovery (`/recover-username/`)

- [ ] Click "Forgot your username?" on login page
- [ ] Enter email address: `test@example.com`
- [ ] Submit
- [ ] See username displayed on page
- [ ] Try invalid email → see error message

---

## 3. REGULAR USER - NAVIGATION & PROFILE

### Navigation Bar (All Pages)

- [ ] See username in top right
- [ ] Hover/click username → see dropdown menu
- [ ] Dropdown shows:
  - [ ] "My Queue" link
  - [ ] "Submit Queue Entry" link
  - [ ] "Profile" link
  - [ ] "Check In/Out" link (if has active jobs)
  - [ ] "Notifications" link
  - [ ] "Archive" link
  - [ ] "Logout" link
- [ ] NO admin links visible for regular users
- [ ] All links navigate to correct pages

### User Profile Page (`/profile/`)

**Profile Information Tab:**
- [ ] See current profile information displayed
- [ ] Edit First Name → save → see success message
- [ ] Edit Last Name → save → see success message
- [ ] Changes reflected on page after refresh
- [ ] Try blank required fields → see validation error

**Notification Preferences Tab:**
- [ ] See list of notification types
- [ ] Toggle "Queue Position: On Deck" → save → see success
- [ ] Toggle "Queue Position: Ready for Check-In" → save (should NOT disable - critical)
- [ ] Toggle "Checkout Reminder" → save (should NOT disable - critical)
- [ ] Toggle other notifications → save → verify saved
- [ ] Refresh page → verify checkboxes reflect saved state
- [ ] See "Followed Presets" section
- [ ] See list of followed presets (if any)

**Security Settings:**
- [ ] Click "Change Security Question"
- [ ] Enter current security answer
- [ ] Select new security question
- [ ] Enter new security answer
- [ ] Submit → see success message
- [ ] Verify change by going through password reset flow

---

## 4. QUEUE MANAGEMENT - REGULAR USER

### Submit Queue Entry (`/schedule/submit/`)

**Test Basic Submission:**
- [ ] See form with all fields
- [ ] Select machine from dropdown
- [ ] Enter job title: "Test Measurement 1"
- [ ] Enter description/notes
- [ ] Enter estimated duration: 2 hours
- [ ] Select priority: Normal
- [ ] Submit form
- [ ] See success message
- [ ] Redirected to "My Queue" page
- [ ] See new entry in "My Upcoming Jobs" section

**Test Rush Job Request:**
- [ ] Fill in form as above
- [ ] Check "Request Rush Job" checkbox
- [ ] Enter rush justification: "Urgent deadline tomorrow"
- [ ] Submit
- [ ] See message about pending admin approval
- [ ] Entry should show "Rush (Pending)" status
- [ ] Admin should see notification about rush request

**Test Preset Loading:**
- [ ] Click "Load Preset" dropdown
- [ ] Select existing preset
- [ ] Verify form fields auto-fill with preset values
- [ ] Modify one field
- [ ] Submit
- [ ] Verify entry uses modified values

**Test Preset Creation:**
- [ ] Fill in form with specific values
- [ ] Click "Save as Preset"
- [ ] Enter preset name: "My Test Preset"
- [ ] Choose visibility: "Private"
- [ ] Submit
- [ ] See success message
- [ ] Refresh page → new preset appears in dropdown
- [ ] Load preset → verify values match

**Test Following Presets:**
- [ ] Load a preset created by ANOTHER user (if available)
- [ ] Click "Follow This Preset" button (if visible)
- [ ] See success message
- [ ] Go to Profile → Notification Preferences
- [ ] See preset in "Followed Presets" section
- [ ] Unfollow from profile → verify removed

**Test Validation Errors:**
- [ ] Submit form with missing machine → see error
- [ ] Submit with missing title → see error
- [ ] Submit with negative duration → see error
- [ ] Submit with duration > 24 hours → see warning/error
- [ ] Submit with missing justification for rush job → see error

### My Queue Page (`/schedule/my-queue/`)

**View My Queue:**
- [ ] See "My Upcoming Jobs" section
- [ ] See entries in order (rush first, then order number)
- [ ] Each entry shows:
  - [ ] Machine assignment
  - [ ] Title
  - [ ] Status (Pending, Ready, Running)
  - [ ] Position in queue
  - [ ] Estimated duration
  - [ ] Rush indicator (if applicable)
- [ ] See "My Completed Jobs" section (last 10)
- [ ] See completed entries with completion dates

**Cancel Queue Entry:**
- [ ] Find a PENDING entry
- [ ] Click "Cancel" button
- [ ] See confirmation dialog
- [ ] Confirm cancellation
- [ ] Entry disappears from list
- [ ] See success message
- [ ] Verify entry is gone after page refresh

**Test Cannot Cancel Running Entry:**
- [ ] Try to cancel entry with status "Running"
- [ ] Should NOT see cancel button (or see error if attempted)
- [ ] Running entries can only be checked out, not cancelled

---

## 5. CHECK-IN/CHECK-OUT FLOW

### Check-In Process

**From My Queue Page:**
- [ ] Find entry with status "Ready for Check-In"
- [ ] Click "Check In" button
- [ ] See confirmation dialog
- [ ] Confirm check-in
- [ ] Entry status changes to "Running"
- [ ] See "Started At" timestamp
- [ ] "Check In" button disappears
- [ ] "Check Out" button appears
- [ ] Estimated completion time displayed

**From Check In/Out Page (`/schedule/check-in-check-out/`):**
- [ ] Visit check-in page
- [ ] See "Ready to Check In" section
- [ ] See entry listed
- [ ] Click "Check In" button
- [ ] See confirmation
- [ ] Entry moves to "Currently Running" section

**Test Reminder Scheduling:**
- [ ] After checking in, verify reminder is scheduled
- [ ] Note the estimated completion time
- [ ] (Hard to test immediately - requires waiting for reminder due time)

### Check-Out Process

**From My Queue Page:**
- [ ] Find entry with status "Running"
- [ ] Click "Check Out" button
- [ ] See form with optional fields:
  - [ ] Actual duration (auto-filled)
  - [ ] Notes/results
  - [ ] Option to save to archive
- [ ] Fill in results/notes
- [ ] Check "Save to Archive" if desired
- [ ] Submit
- [ ] Entry status changes to "Completed"
- [ ] See "Completed At" timestamp
- [ ] Entry moves to "Completed" section
- [ ] If archived, see success message with archive link

**From Check In/Out Page:**
- [ ] See "Currently Running" section
- [ ] Find running entry
- [ ] Click "Check Out" button
- [ ] Fill in checkout form
- [ ] Submit
- [ ] Entry disappears from "Running" section
- [ ] Moves to "Recent Completions" (if shown)

**Test Early/Late Checkout:**
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

- [ ] Visit archive page
- [ ] See list of archived measurements
- [ ] Filter by machine → dropdown filters list
- [ ] Search by title → results filter correctly
- [ ] See columns: Machine, Date, Title, Notes, Actions
- [ ] Pagination works (if > 20 entries)

### Create Archive Entry (`/schedule/archive/create/`)

- [ ] Click "New Archive Entry"
- [ ] Select machine
- [ ] Enter measurement date (date picker)
- [ ] Enter title: "Manual Archive Test"
- [ ] Enter notes/results
- [ ] Upload file (optional) - test with small CSV/PDF
- [ ] Submit
- [ ] See success message
- [ ] Entry appears in archive list
- [ ] Download file → verify correct file downloads

### Save from Queue Entry

- [ ] During check-out, enable "Save to Archive"
- [ ] Fill in optional notes
- [ ] Submit checkout
- [ ] Go to archive page
- [ ] Verify entry was created with:
  - [ ] Correct machine
  - [ ] Correct date (check-in date)
  - [ ] Queue entry title
  - [ ] Any notes added

### Export My Measurements

- [ ] Click "Export My Measurements" button
- [ ] See CSV file download
- [ ] Open CSV in spreadsheet app
- [ ] Verify contains:
  - [ ] All YOUR archived measurements (not others')
  - [ ] Correct columns: ID, Machine, Date, Title, Notes, Archived At
  - [ ] Data is accurate

### Bulk Delete Archives

**Staff Only - Skip if Regular User**

### Delete Single Archive Entry

- [ ] Find an archive entry YOU created
- [ ] Click "Delete" button
- [ ] See confirmation dialog
- [ ] Confirm deletion
- [ ] Entry disappears from list
- [ ] See success message
- [ ] Try to delete entry created by ANOTHER user
- [ ] Should NOT see delete button (or get error)

### Download Archive Files

- [ ] Find entry with uploaded file
- [ ] Click "Download" link
- [ ] File downloads correctly
- [ ] File is the correct file (not corrupted)
- [ ] Verify filename matches original upload

---

## 7. PRESET MANAGEMENT - REGULAR USER

### View Preset (`/schedule/preset/view/<id>/`)

- [ ] Navigate to preset view (from submit page "View" link)
- [ ] See preset details:
  - [ ] Name
  - [ ] Creator
  - [ ] Visibility (Private/Lab/Public)
  - [ ] Machine
  - [ ] Estimated duration
  - [ ] Description/notes
  - [ ] Fields (if any custom fields)
- [ ] See "Use This Preset" button → redirects to submit page with preset loaded

### Create Preset (from Submit Page)

- [ ] Fill in queue submission form
- [ ] Click "Save as Preset" button
- [ ] See preset creation modal
- [ ] Enter name: "New Test Preset"
- [ ] Select visibility: "Lab Members"
- [ ] Submit
- [ ] See success message
- [ ] Preset appears in dropdown on submit page
- [ ] Verify preset is saved correctly

### Edit Preset (`/schedule/preset/edit/<id>/`)

- [ ] From submit page, select YOUR preset
- [ ] Click "Edit Preset" button
- [ ] See preset edit form
- [ ] Change preset name: "Updated Preset Name"
- [ ] Change visibility: "Public"
- [ ] Modify default duration
- [ ] Submit
- [ ] See success message
- [ ] Reload submit page → verify changes reflected
- [ ] Try to edit ANOTHER user's preset
- [ ] Should get permission denied error (unless preset is shared and editable)

### Copy Preset (`/schedule/preset/copy/<id>/`)

- [ ] Select ANY preset (yours or others')
- [ ] Click "Copy Preset" button
- [ ] See copy form with preset values pre-filled
- [ ] Change name: "Copied from X"
- [ ] Change visibility if desired
- [ ] Submit
- [ ] See success message
- [ ] New preset appears in YOUR preset list
- [ ] Verify it's a separate copy (editing it doesn't affect original)

### Delete Preset

- [ ] Select YOUR preset from dropdown
- [ ] Click "Delete Preset" button
- [ ] See confirmation dialog (possibly Thanos modal if implemented)
- [ ] Confirm deletion
- [ ] Preset disappears from dropdown
- [ ] See success message
- [ ] Try to delete preset you DON'T own
- [ ] Should not see delete button or get permission error

### Follow/Unfollow Presets

**Follow Preset:**
- [ ] Load a preset created by ANOTHER user
- [ ] Click "Follow This Preset" button
- [ ] See success message
- [ ] Go to Profile → Notification Preferences
- [ ] See preset listed in "Followed Presets"
- [ ] When preset is updated, you should get notification (test later)

**Unfollow Preset:**
- [ ] From Profile page, find followed preset
- [ ] Click "Unfollow" button
- [ ] Preset removed from list
- [ ] No longer receive updates about this preset

---

## 8. NOTIFICATIONS - REGULAR USER

### View Notifications (`/schedule/notifications/`)

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

- [ ] Verify SLACK_BOT_TOKEN is set in Render environment
- [ ] Verify YOUR user has Slack User ID configured in profile
- [ ] Verify Slack bot is installed in workspace

### Test Slack Notifications

**For each notification type above, verify Slack DM is received:**

**Ready for Check-In (Slack):**
- [ ] Trigger "ready for check-in" event
- [ ] Check Slack DMs from bot
- [ ] Should receive message about job ready
- [ ] Message includes one-time login link
- [ ] Click link → should auto-login and redirect to check-in page

**Checkout Reminder (Slack):**
- [ ] Trigger checkout reminder
- [ ] Check Slack DMs
- [ ] Should receive reminder message
- [ ] Message includes login link to checkout page

**Rush Job Approved/Rejected (Slack):**
- [ ] Trigger rush job decision
- [ ] Check Slack DMs
- [ ] Should receive notification with decision

**One-Time Login Token:**
- [ ] Receive Slack notification with link
- [ ] Click link → should auto-login
- [ ] Should redirect to intended page (check-in, queue, etc.)
- [ ] Token should work multiple times (not consumed on first use)
- [ ] After 24 hours, token should expire
- [ ] Expired token shows error message

**Test Wrong User Token Login:**
- [ ] Get notification link meant for test_user1
- [ ] Log in as test_user2
- [ ] Click test_user1's notification link
- [ ] Should be logged out automatically
- [ ] Should see message: "This link is for test_user1..."
- [ ] Should be prompted to login as correct user

---

## 10. ADMIN DASHBOARD - STAFF USERS ONLY

### Access Admin Dashboard

**Login as test_admin (staff user):**
- [ ] See "Admin Dashboard" link in navigation dropdown
- [ ] Click → navigate to `/schedule/admin-dashboard/`
- [ ] See dashboard with widgets:
  - [ ] Total Users
  - [ ] Pending Approvals
  - [ ] Active Queue Entries
  - [ ] Total Machines
  - [ ] Rush Job Requests
- [ ] See navigation cards for:
  - [ ] User Management
  - [ ] Queue Management
  - [ ] Machine Management
  - [ ] Preset Management
  - [ ] Database Management
  - [ ] Storage Stats
  - [ ] Rush Job Review

**Test Regular User Access:**
- [ ] Login as test_user1 (non-staff)
- [ ] Try accessing `/schedule/admin-dashboard/` directly
- [ ] Should get "Permission Denied" error or redirect

---

## 11. USER MANAGEMENT - ADMIN

### View Users (`/schedule/admin-users/`)

- [ ] See list of all users
- [ ] Each user shows:
  - [ ] Username
  - [ ] Email
  - [ ] Name
  - [ ] Approval status
  - [ ] Staff status
  - [ ] Date joined
  - [ ] Actions (Approve/Reject/Delete/Promote/Demote)
- [ ] See separate sections:
  - [ ] Pending Approvals (highlighted)
  - [ ] Approved Users
  - [ ] Rejected Users

### Approve User

- [ ] Find test_unapproved in pending list
- [ ] Click "Approve" button
- [ ] See confirmation
- [ ] User moves to "Approved Users" section
- [ ] User receives notification (check in their account)
- [ ] User can now login and access site

### Reject User

- [ ] Create new test account that needs approval
- [ ] In admin panel, click "Reject" button
- [ ] Enter rejection reason: "Test rejection"
- [ ] Submit
- [ ] User moves to "Rejected Users" section
- [ ] User receives notification with reason
- [ ] User still cannot login

### Delete User

- [ ] Find user you want to delete (NOT yourself)
- [ ] Click "Delete" button
- [ ] See confirmation dialog (warning about data deletion)
- [ ] Confirm deletion
- [ ] User removed from list
- [ ] User's data (queue entries, archives) should be deleted or orphaned
- [ ] User cannot login anymore

### Promote to Staff

- [ ] Find approved regular user (test_user1)
- [ ] Click "Promote to Staff" button
- [ ] See confirmation
- [ ] User now shows as "Staff: Yes"
- [ ] User receives notification about promotion
- [ ] Login as that user → should see admin links now

### Demote from Staff

- [ ] Find staff user (not yourself, not superuser)
- [ ] Click "Demote from Staff" button
- [ ] See confirmation
- [ ] User no longer shows as staff
- [ ] User receives notification
- [ ] Login as that user → admin links disappear

### Test Cannot Demote Self

- [ ] Try to demote your own account
- [ ] Should see error message
- [ ] Action should be blocked

---

## 12. MACHINE MANAGEMENT - ADMIN

### View Machines (`/schedule/admin-machines/`)

- [ ] See list of all machines
- [ ] Each machine shows:
  - [ ] Name
  - [ ] Slug (URL identifier)
  - [ ] Description
  - [ ] Status (Online/Offline/Maintenance)
  - [ ] Temperature (if available)
  - [ ] Last updated
  - [ ] Actions (Edit/Delete)

### Add Machine

- [ ] Click "Add New Machine" button
- [ ] Fill in form:
  - [ ] Name: "Test Machine 4"
  - [ ] Slug: "test-machine-4" (auto-generated or manual)
  - [ ] Description: "Test equipment for testing"
  - [ ] Status: "Online"
- [ ] Submit
- [ ] See success message
- [ ] Machine appears in list
- [ ] Machine appears in queue submission dropdown

### Edit Machine

- [ ] Click "Edit" on existing machine
- [ ] Change name: "Updated Test Machine"
- [ ] Change status: "Maintenance"
- [ ] Change description
- [ ] Submit
- [ ] See success message
- [ ] Changes reflected in machine list
- [ ] Changes reflected in public pages (queue, fridges)

### Delete Machine

**Test Cannot Delete with Active Queue Entries:**
- [ ] Find machine with pending/running queue entries
- [ ] Click "Delete" button
- [ ] Should see error: "Cannot delete machine with active queue entries"
- [ ] Machine remains in list

**Test Successful Deletion:**
- [ ] Find machine with NO queue entries
- [ ] Click "Delete" button
- [ ] See confirmation dialog
- [ ] Confirm deletion
- [ ] Machine removed from list
- [ ] Machine no longer appears in dropdowns

### Temperature Updates (If temperature gateway configured)

- [ ] Check machine temperature display
- [ ] If temperature gateway is running:
  - [ ] See actual temperature values
  - [ ] See last updated timestamp
  - [ ] Temperature updates every 5 minutes
- [ ] If no temperature gateway:
  - [ ] Temperature shows as "None" or "N/A"

---

## 13. QUEUE MANAGEMENT - ADMIN

### View Admin Queue (`/schedule/admin-queue/`)

- [ ] See comprehensive queue view
- [ ] Sections:
  - [ ] All Pending Entries (ordered)
  - [ ] Running Entries
  - [ ] Recently Completed
- [ ] Each entry shows:
  - [ ] Position number
  - [ ] User
  - [ ] Machine
  - [ ] Title
  - [ ] Status
  - [ ] Rush indicator
  - [ ] Estimated duration
  - [ ] Actions

### Edit Queue Entry

- [ ] Click "Edit" on any entry
- [ ] See edit form with all fields
- [ ] Change machine assignment
- [ ] Change estimated duration
- [ ] Change notes
- [ ] Submit
- [ ] See success message
- [ ] Changes reflected in queue
- [ ] User receives notification about changes

### Cancel Queue Entry (Admin)

- [ ] Click "Cancel" on any entry
- [ ] Enter cancellation reason: "Admin test cancellation"
- [ ] Submit
- [ ] Entry removed from queue
- [ ] User receives notification with reason

### Move Entry Up in Queue

- [ ] Find entry at position #5 or higher
- [ ] Click "Move Up" button
- [ ] Entry moves to position #4
- [ ] Order numbers adjust for other entries
- [ ] Click repeatedly → entry continues moving up
- [ ] Cannot move above position #1

### Move Entry Down in Queue

- [ ] Find entry near top of queue
- [ ] Click "Move Down" button
- [ ] Entry moves down one position
- [ ] Other entries adjust
- [ ] Click repeatedly → entry continues moving down

### Queue Next (Jump to Position #1)

- [ ] Find entry at position #7
- [ ] Click "Queue Next" button
- [ ] See confirmation
- [ ] Entry jumps to position #1
- [ ] All other entries shift down
- [ ] User receives "Ready for Check-In" notification

### Reassign Machine

- [ ] Click "Reassign Machine" on entry
- [ ] See dropdown with all machines
- [ ] Select different machine
- [ ] Submit
- [ ] Machine assignment updated
- [ ] Entry position may change based on new machine's queue
- [ ] User receives notification about change

### Admin Check-In (For User)

- [ ] Find entry at position #1 (ready to check in)
- [ ] Click "Check In" button
- [ ] Entry status changes to "Running"
- [ ] Started timestamp recorded
- [ ] User receives notification
- [ ] Reminder scheduled

### Admin Check-Out (For User)

- [ ] Find running entry
- [ ] Click "Check Out" button
- [ ] Fill in completion form (optional notes)
- [ ] Submit
- [ ] Entry status changes to "Completed"
- [ ] Completed timestamp recorded
- [ ] User receives notification
- [ ] Next entry in queue becomes "Ready"

---

## 14. RUSH JOB REVIEW - ADMIN

### View Rush Job Requests (`/schedule/admin-rush-jobs/`)

- [ ] See list of pending rush job requests
- [ ] Each request shows:
  - [ ] User
  - [ ] Machine
  - [ ] Title
  - [ ] Justification
  - [ ] Requested date
  - [ ] Actions (Approve/Reject)
- [ ] If no requests, see "No pending rush job requests" message

### Approve Rush Job

- [ ] Have test_user1 submit rush job request
- [ ] In admin panel, see request appear
- [ ] Click "Approve" button
- [ ] Entry marked as "Rush"
- [ ] Entry moves to front of queue (position #1 or near top)
- [ ] User receives "Rush job approved" notification
- [ ] Request disappears from pending list

### Reject Rush Job

- [ ] Have test_user2 submit rush job request
- [ ] Click "Reject" button
- [ ] Enter rejection reason: "Insufficient justification"
- [ ] Submit
- [ ] Entry remains in queue at regular position (not rushed)
- [ ] User receives "Rush job rejected" notification with reason
- [ ] Request disappears from pending list

---

## 15. PRESET MANAGEMENT - ADMIN

### View All Presets (`/schedule/admin-presets/`)

- [ ] See list of ALL presets (all users, all visibility levels)
- [ ] Each preset shows:
  - [ ] Name
  - [ ] Creator
  - [ ] Visibility
  - [ ] Machine
  - [ ] Created date
  - [ ] Actions (View/Edit/Delete)
- [ ] Filter by visibility: Private/Lab/Public
- [ ] Filter by creator

### Admin Edit Any Preset

- [ ] Click "Edit" on preset created by ANOTHER user
- [ ] See edit form
- [ ] Make changes
- [ ] Submit
- [ ] Changes saved
- [ ] Creator receives notification about admin edit

### Admin Delete Any Preset

- [ ] Click "Delete" on any preset
- [ ] See confirmation (Thanos modal if implemented)
- [ ] Confirm deletion
- [ ] Preset removed
- [ ] Users following this preset receive notification

---

## 16. DATABASE MANAGEMENT - ADMIN

### View Storage Stats (`/schedule/admin/storage-stats/`)

- [ ] See database size information
- [ ] See storage usage percentage
- [ ] See breakdown by table:
  - [ ] Queue Entries
  - [ ] Archived Measurements
  - [ ] Users
  - [ ] Notifications
  - [ ] Sessions
- [ ] See total size in MB
- [ ] See warning if over threshold (>80% of 3GB for Neon)

### Export Full Database

- [ ] Click "Export Entire Database" button
- [ ] See download start immediately (or after short processing)
- [ ] Download completes with JSON file
- [ ] Filename format: `database_backup_YYYY-MM-DD_HH-MM-SS.json`
- [ ] File size should be reasonable (check it's not empty)
- [ ] Open file → verify it's valid JSON
- [ ] Should contain all tables: users, queue entries, machines, etc.

### Export Archive Only

- [ ] Click "Export Archive Only" button
- [ ] Download JSON file
- [ ] Open file → verify it contains only archived measurements
- [ ] Should NOT include users, queue entries, etc.

### Import/Restore Database

**Test Replace Mode:**
- [ ] Click "Import/Restore Database" button
- [ ] Select mode: "Replace (Delete existing data)"
- [ ] Upload backup JSON file (from previous export)
- [ ] See Thanos modal warning
- [ ] Type "CONFIRM RESTORE" in text box
- [ ] Submit
- [ ] See processing message
- [ ] See success message after completion
- [ ] Verify data was restored:
  - [ ] Check queue entries match backup
  - [ ] Check users match backup
  - [ ] Check machines match backup
  - [ ] Current data was wiped and replaced

**Test Merge Mode:**
- [ ] Make note of current database state (count entries)
- [ ] Upload backup JSON with DIFFERENT data
- [ ] Select mode: "Merge (Keep existing data)"
- [ ] See Thanos modal
- [ ] Type "CONFIRM RESTORE"
- [ ] Submit
- [ ] See success message
- [ ] Verify data was merged:
  - [ ] Old entries still exist
  - [ ] New entries from backup added
  - [ ] Duplicate entries handled appropriately
  - [ ] Entry count increased

**Test Validation Errors:**
- [ ] Try to upload invalid JSON file → see error
- [ ] Try to upload JSON with wrong structure → see error
- [ ] Try without typing "CONFIRM RESTORE" → submission blocked

### Clear Archive with Backup

- [ ] Click "Clear Archive with Backup" button
- [ ] See confirmation
- [ ] Download backup JSON starts
- [ ] After download, archive data is cleared
- [ ] Archive page shows 0 entries
- [ ] Backup file contains all deleted archives
- [ ] Other data (users, queue) unaffected

### Clear Archive (Without Backup)

- [ ] Click "Clear Archive" button (dangerous action)
- [ ] See strong warning message
- [ ] See Thanos modal with text confirmation
- [ ] Type confirmation text
- [ ] Submit
- [ ] All archived measurements deleted
- [ ] Archive page shows 0 entries
- [ ] NO backup file generated
- [ ] Other data unaffected

---

## 17. RENDER USAGE STATS - ADMIN (Optional)

### View Render Usage (`/schedule/admin/render-usage/`)

- [ ] See usage statistics (if implemented)
- [ ] See request count for current month
- [ ] See estimated uptime hours
- [ ] See percentage of free tier limit used
- [ ] See days remaining in month
- [ ] Color coding: green (<80%), yellow (80-95%), red (>95%)

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

**Test Queue Position Updates:**
- [ ] Open queue page in two tabs
- [ ] Tab 1: Admin moves entry up
- [ ] Tab 2: Refresh → should see new position
- [ ] Both tabs should show consistent order

### Invalid URLs

- [ ] Try accessing `/schedule/edit/9999999/` (non-existent entry)
- [ ] Should see 404 error
- [ ] Try accessing `/schedule/preset/view/9999/` (non-existent preset)
- [ ] Should see 404 error
- [ ] Try accessing deleted entry URL
- [ ] Should see 404 or "Entry not found" message

### Permission Errors

**Regular User Accessing Admin Pages:**
- [ ] Login as regular user
- [ ] Try accessing `/schedule/admin-dashboard/` directly
- [ ] Should see "Permission Denied" error or redirect to home
- [ ] Try accessing `/schedule/admin-users/` directly
- [ ] Should see error/redirect

**User Editing Other User's Data:**
- [ ] Login as test_user1
- [ ] Try to cancel test_user2's queue entry (if URL guessable)
- [ ] Should see "Permission Denied" error
- [ ] Try to edit test_user2's preset
- [ ] Should see error

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

**Archive File Upload:**
- [ ] Try uploading very large file (>10MB)
- [ ] Should see error or file rejected
- [ ] Try uploading invalid file type (.exe, .sh)
- [ ] Should see error
- [ ] Try uploading file with special characters in name
- [ ] Should be sanitized or rejected

### Cross-Site Request Forgery (CSRF)

- [ ] All forms should have CSRF token
- [ ] Try submitting form without CSRF token (use browser dev tools)
- [ ] Should see "CSRF token missing" error
- [ ] Form submission should be rejected

---

## 19. WEBSOCKET REAL-TIME UPDATES (Production Only)

**Note:** These only work on production (Render with Daphne), not local runserver

### Queue Updates

- [ ] Open queue page in two browsers (different users)
- [ ] Browser 1: Admin moves entry in queue
- [ ] Browser 2: Should see entry position update WITHOUT refresh
- [ ] Test with multiple simultaneous admins

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
- [ ] Menu collapses to hamburger icon on small screens
- [ ] Hamburger menu opens/closes correctly
- [ ] All links accessible on mobile
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

- [ ] Cannot access authenticated pages without login
- [ ] Session expires after inactivity (7 days for non-remember-me)
- [ ] Logout completely clears session
- [ ] Cannot reuse old session cookies after logout

### Authorization

- [ ] Regular users cannot access admin pages
- [ ] Users cannot modify other users' data
- [ ] Staff-only features blocked for regular users
- [ ] Superuser features blocked for non-superusers

### SQL Injection Prevention

- [ ] Try entering `' OR '1'='1` in search fields
- [ ] Should NOT cause SQL errors
- [ ] Should NOT bypass authentication
- [ ] Django ORM should parameterize queries

### XSS Prevention

- [ ] Enter `<script>alert('XSS')</script>` in form fields
- [ ] Should be escaped/sanitized when displayed
- [ ] Should NOT execute as JavaScript
- [ ] Check queue title, notes, preset names

### CSRF Protection

- [ ] All forms include CSRF token
- [ ] Cannot submit forms from external sites
- [ ] CSRF token validated on submission

---

## 24. DATA INTEGRITY

### Cascading Deletes

**Delete User with Data:**
- [ ] Create user with queue entries and archives
- [ ] Delete user via admin panel
- [ ] Verify user's queue entries are handled (deleted or orphaned)
- [ ] Verify user's archives are handled appropriately
- [ ] No orphaned data in database

**Delete Machine with Data:**
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
- [ ] Email must be valid format
- [ ] Username must be unique
- [ ] Password must meet complexity requirements
- [ ] Required fields enforced

### Timestamps

- [ ] Created timestamps set automatically
- [ ] Updated timestamps change on edit
- [ ] Timezone-aware timestamps stored correctly
- [ ] Times display in correct timezone for user

---

## 25. BACKUP & RECOVERY

### Test Database Export/Import Cycle

1. **Export Current Database:**
   - [ ] Export full database
   - [ ] Note counts: X users, Y queue entries, Z archives

2. **Make Changes:**
   - [ ] Add 5 new queue entries
   - [ ] Delete 2 users
   - [ ] Create 3 new presets

3. **Restore from Backup:**
   - [ ] Import backup in "Replace" mode
   - [ ] Verify counts match original (X users, Y entries, Z archives)
   - [ ] Verify recent changes are gone (back to backup state)

4. **Test Merge Mode:**
   - [ ] Make backup of current state
   - [ ] Add new data
   - [ ] Import backup in "Merge" mode
   - [ ] Verify OLD data exists
   - [ ] Verify NEW data also exists
   - [ ] No duplicates created

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
