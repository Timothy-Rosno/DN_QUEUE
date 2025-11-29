# Implementation Plan for Scheduler App TODO Items

## Phase 1: Critical Bug Fixes & Data Integrity (URGENT)

### 1.1 Fix Preset-User Dependency Bug ⚠️ **HIGHEST PRIORITY**
**Problem:** Presets are deleted when users are deleted (CASCADE)
**Solution:**
- Change `QueuePreset.creator` from `CASCADE` to `SET_NULL` with author stored as CharField
- Add `creator_username` CharField to preserve author name
- Update `display_name` generation to use username string instead of User object
- Create migration to backfill existing presets with creator usernames
- Update all views/forms that reference `preset.creator`

### 1.2 Auto-follow Own Presets
- Update preset creation view to automatically add creator to followers
- Works for both public and private presets
- Enable appropriate notifications by default

### 1.3 Rush Job Deletion Notification
- Update rush job deletion view to send admin notification
- Message: "Rush job deleted by [username]: [job title]"
- Clear/update related notifications when rush job is deleted

### 1.4 Machine Status Update on Deletion
- When running/on-deck queue entries are deleted by admin:
  - Update machine status to 'idle' if was running
  - Recalculate queue positions
  - Notify next person if they become on-deck
- Add admin confirmation modal for deletions with warnings

### 1.5 Multiple ON DECK Display
- Update queue display logic to show ALL position #1 entries (across different machines)
- Create dedicated ON DECK section in My Queue view
- Update notifications to handle multiple on-deck entries

## Phase 2: UI/UX Improvements (AESTHETICS)

### 2.1 Replace Alert Boxes with Banner Notifications
- Create dismissible banner component for non-critical messages
- Keep modal confirmations only for destructive actions (delete account, delete preset, etc.)
- Implement toast notifications for success messages
- Update all `messages.success/info/warning` to use new banner system

### 2.2 Standardize Button Styles
- Create consistent button classes in base.css
- Audit all templates for button usage
- Priority: Admin pages (dashboard, users, machines, rush jobs)
- Ensure consistent sizing, positioning, spacing across all pages

### 2.3 Auto-logout After 30 Minutes Inactivity
- Implement Django session timeout middleware
- Add JavaScript to warn user at 28 minutes
- Redirect to login with message about timeout
- Preserve redirect URL to return after re-login

### 2.4 Move Machine Specs to "Fridge List" Page
- Create new route `/fridges/` with machine specifications
- Home page shows only: Machine name, status, queue (positions 1-3, then user's position if 4+)
- Add "View Specifications" link to new Fridge List page
- Fridge List shows full specs table for all machines

### 2.5 Machine Status Overview Enhancement
- Create per-machine countdown display on home page
- Show estimated time remaining for current job
- Show total queue wait time
- Similar to admin overview but per-machine for users

## Phase 3: Enhanced Notification System (URGENT)

### 3.1 Notification Routing on Click
**Routing map:**
- `admin_new_user` → User Approval page (`/admin/users/`)
- `admin_rush_job` → Rush Job Management (`/admin/rush-jobs/`)
- `preset_*` → Submit Queue page with preset loaded
- `queue_position_change` → My Queue page
- `on_deck` → Check-in/Check-out page (new)
- `job_completed` → Check-in/Check-out page (new)
- `job_started` → My Queue page

**Implementation:**
- Add `get_notification_url()` method to Notification model
- Update notification display to use `<a>` tags instead of just text
- Mark as read when clicked

### 3.2 Notification Bulk Actions
- Add "Clear Read Notifications" button in navbar dropdown
- Add "Mark All as Read" button
- Add individual "Dismiss" X button per notification (without routing)
- Keep individual click for routing + mark as read

### 3.3 Create Check-in/Check-out Page
- New route: `/queue/check-in-check-out/`
- Shows current on-deck entries for user
- Check-in button for each on-deck entry
- Check-out button for running entries
- Status display and machine info
- Route from on-deck notifications here

## Phase 4: Settings & Configuration (URGENT)

### 4.1 Default Settings Button
- Add "Reset to Defaults" button in Profile notification preferences
- Confirmation modal before reset
- Use existing default values from NotificationPreference model
- Success message after reset

### 4.2 Character Limits (500 chars)
- Add maxlength="500" to all text inputs/textareas
- Add character counter showing remaining characters (starts at 475, warning at yellow, red at 490)
- Fields to update: preset names, descriptions, titles, notes, special requirements, etc.
- Client-side and server-side validation

## Phase 5: Archived Measurements System (URGENT)

### 5.1 Database Structure
- Create `ArchivedMeasurement` model
- Fields: user, machine, preset_snapshot (JSON), measurement_date, uploaded_files, notes, status
- Organize by year/month in file storage

### 5.2 Archive Views
- Global archive view: `/archive/` with year/month dropdowns (defaults to current month)
- Filter by machine, user (admin only), date range
- Display as table with: Date, User, Machine, Preset, Files, Notes
- Download files functionality

### 5.3 User Archive Integration
- Add archive link from completed queue entries
- "Save to Archive" button after job completion
- Auto-archive option in queue entry submission (checkbox)

## Phase 6: Code Cleanup (CLARITY)

### 6.1 Archive Legacy Code
- Move legacy templates to `templates/legacy_archive/` (rename folder)
- Move test files to `tests/archive_v1/`
- Add README.md in archive folders explaining v2 removal plan
- Ensure no active references to archived files

### 6.2 Remove Unused Code
- Audit views.py for unused functions
- Remove old schedule-related code (replaced by queue system)
- Clean up unused imports
- Run tests to ensure nothing breaks

## Phase 7: Machine Communication (MACHINE) - Research Phase

### 7.1 Design Static IP API System
- Research: Can we ping machine IPs from Django server?
- Design API endpoints on machine computers to return:
  - Current temperature
  - Current B-field
  - Measurement progress (if available)
  - Sample loader status (Kiutra)
- Document API structure for each machine type

### 7.2 Local File System Approach
- Each machine writes to local status file
- Django pings machine IP to GET status file
- Variables: temp, b_field, progress_percent, estimated_time_remaining
- Test with one machine first (Kiutra recommended - hosts on same computer)

### 7.3 Machine-Specific Implementations
**Priority Order:**
1. **Kiutra** - Already on control computer, no IP complexity
2. **OptiCool** - Temperature controller with static IP
3. **Hidalgo/Griffin** - Temp controllers with static IPs (FSE communication)

## Phase 8: Admin Functionality Migration (AESTHETICS - Future)

### 8.1 Replicate Django Admin Features
- User management (already exists)
- Machine CRUD operations
- Queue entry management
- Preset management (already mostly exists)
- Archive management

### 8.2 Remove Django Admin Dependency
- Lock down `/admin/` route to superuser only
- All staff should use custom admin pages
- Better UI/UX than Django default

---

## Suggested Implementation Order

1. **Week 1:** Phase 1 (Critical bugs) - Items 1.1, 1.3, 1.4
2. **Week 2:** Phase 3 (Notifications) + Phase 4 (Settings)
3. **Week 3:** Phase 5 (Archive system) + remaining Phase 1
4. **Week 4:** Phase 2 (UI/UX improvements)
5. **Week 5:** Phase 6 (Code cleanup)
6. **Week 6+:** Phase 7 (Machine communication - ongoing research)

**Estimated Total:** 6-8 weeks for core features, machine communication ongoing

---

## Progress Tracking

- [ ] Phase 1.1 - Fix Preset-User Dependency
- [ ] Phase 1.2 - Auto-follow Own Presets
- [ ] Phase 1.3 - Rush Job Deletion Notification
- [ ] Phase 1.4 - Machine Status Update on Deletion
- [ ] Phase 1.5 - Multiple ON DECK Display
- [ ] Phase 2.1 - Banner Notifications
- [ ] Phase 2.2 - Standardize Buttons
- [ ] Phase 2.3 - Auto-logout
- [ ] Phase 2.4 - Fridge List Page
- [ ] Phase 2.5 - Machine Status Overview
- [ ] Phase 3.1 - Notification Routing
- [ ] Phase 3.2 - Notification Bulk Actions
- [ ] Phase 3.3 - Check-in/Check-out Page
- [ ] Phase 4.1 - Default Settings Button
- [ ] Phase 4.2 - Character Limits
- [x] Phase 5.1 - Archive Database
- [x] Phase 5.2 - Archive Views
- [x] Phase 5.3 - User Archive Integration
- [ ] Phase 6.1 - Archive Legacy Code
- [ ] Phase 6.2 - Remove Unused Code
- [ ] Phase 7.1 - Design Machine API
- [ ] Phase 7.2 - Local File System
- [ ] Phase 7.3 - Machine Implementations
