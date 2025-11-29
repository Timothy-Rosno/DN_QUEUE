# Enhanced Schedule Entry Form & Queue Management System

## Summary of Changes

This implementation enhances the scheduler application with improved form validation, hierarchical UI, machine matching, and rush job management capabilities.

---

## 1. Model Updates

### QueueEntry Model (`calendarEditor/models.py`)

**New Fields:**
- `is_rush_job` - BooleanField to flag rush job appeals
- `rush_job_submitted_at` - DateTimeField to track when rush job was submitted

**Migration:** `calendarEditor/migrations/0004_queueentry_is_rush_job_and_more.py`

---

## 2. Form Updates

### QueueEntryForm (`calendarEditor/forms.py`)

**Updated Field Labels:**
- `title` → "Device Name" (minimum 3 characters)
- `description` → "Measurement Description" (minimum 15 characters)
- `requires_optical` → "Requires Optical Capabilities (not yet used in matching)"
- `estimated_duration_hours` → Updated help text: "Estimated as cooldown time × 2"
- `is_rush_job` → "Rush Job Appeal"

**Custom Validation:**
- `clean_title()`: Validates minimum 3 characters, error message: "Not long enough."
- `clean_description()`: Validates minimum 15 characters, error message: "Not long enough."

**New Field:** `is_rush_job` checkbox added to form

---

## 3. Matching Algorithm Updates

### `calendarEditor/matching_algorithm.py`

**Changes:**
- **Disabled optical filtering** (lines 169-177): Optical capability is captured in the form but NOT used for machine matching (as requested)
- **Verified lowest wait time selection** (lines 183-207): Algorithm already selects machine with earliest availability, optimizing for lowest user wait times

**New Functions:**
- `move_queue_entry_up(entry_id)`: Move queue entry up one position
- `move_queue_entry_down(entry_id)`: Move queue entry down one position
- `set_queue_position(entry_id, new_position)`: Set queue entry to specific position

---

## 4. Views & Email Notifications

### `calendarEditor/views.py`

**Updated:**
- `submit_queue_entry()`:
  - Sets `rush_job_submitted_at` timestamp when rush job is submitted
  - Sends email notification to admins when rush job is flagged
  - Displays rush job confirmation message

**New Functions:**
- `send_rush_job_notification(queue_entry, request)`: Sends detailed email to all admin users when rush job is submitted
- `is_staff(user)`: Helper function to check staff status
- `admin_rush_jobs(request)`: Admin view showing all rush job appeals grouped by machine
- `admin_move_queue_entry(request, entry_id, direction)`: Move queue entries up/down
- `admin_set_queue_position(request, entry_id)`: Set specific queue position

**Email Notification Details:**
- Sent to all users with `is_staff=True`
- Includes: user info, device name, requirements, assigned machine, queue position, estimated start time
- Provides direct link to admin rush job management page

---

## 5. URL Routing

### `calendarEditor/urls.py`

**New Routes:**
- `/admin/rush-jobs/` - Rush job management interface (staff only)
- `/admin/move/<entry_id>/<direction>/` - Move queue entry up/down (staff only)
- `/admin/set-position/<entry_id>/` - Set queue entry position (staff only)

---

## 6. Templates

### Updated: `templates/calendarEditor/submit_queue.html`

**Hierarchical B-field UI:**
- Main checkbox: "Require Magnetic B-field"
  - If checked, shows X, Y, Z axis checkboxes
  - Each axis checkbox reveals Tesla strength input field
  - If Z-axis checked, reveals parallel/perpendicular direction selector
- JavaScript handles conditional show/hide logic
- Form state preserved on validation errors

**Form Features:**
- Custom rendering for all fields with proper labels and help text
- Error messages displayed inline
- Rush job checkbox prominently highlighted in red box

### New: `templates/calendarEditor/admin_rush_jobs.html`

**Admin Rush Job Management Interface:**
- Shows total count of active rush jobs
- Groups rush jobs by assigned machine
- Displays full queue context for each machine

**For Each Rush Job:**
- User information and contact details
- Full requirement specifications
- Queue position and estimated start time
- Special requirements and description

**Queue Management Controls:**
- ↑ Move Up button (disabled if already at position 1)
- ↓ Move Down button
- Direct position input field with "Set" button
- Full queue table showing all entries with rush job indicators

---

## 7. Settings Configuration

### `mysite/settings.py`

**Email Configuration Added:**
- **Development**: `EMAIL_BACKEND = 'console'` (emails print to console)
- **Production**: SMTP settings template provided (commented out)
- `DEFAULT_FROM_EMAIL = 'scheduler@example.com'`

---

## 8. How the System Works

### User Submission Flow:

1. User fills out enhanced form with:
   - Device Name (min 3 chars)
   - Measurement Description (min 15 chars)
   - Temperature requirements (min/max)
   - B-field requirements (hierarchical checkbox UI)
   - DC/RF line counts
   - Optional daughterboard requirement
   - Optical capability flag (not used in matching yet)
   - Estimated duration
   - Optional rush job appeal checkbox

2. System finds best matching machine:
   - Filters by temperature capabilities
   - Filters by B-field strength (X, Y, Z)
   - Filters by B-field direction (parallel/perpendicular/both)
   - Filters by DC/RF line availability
   - Filters by daughterboard compatibility
   - **Skips optical filtering** (form-only for now)
   - Selects machine with **lowest projected wait time**

3. Request assigned to queue of best machine

4. If rush job flagged:
   - Sets `rush_job_submitted_at` timestamp
   - Sends email to all admin users
   - Displays confirmation to user

### Admin Management Flow:

1. Admin receives email notification about rush job

2. Admin navigates to `/admin/rush-jobs/` URL

3. Admin views:
   - All rush job appeals grouped by machine
   - Full queue context for each machine
   - Detailed requirements and user information

4. Admin can:
   - Move entries up/down with arrow buttons
   - Set specific queue position with input field
   - Review all requirements before making decisions
   - See updated estimated start times after reordering

---

## 9. Key Features Implemented

✅ **Form Validation:**
- Device Name: minimum 3 characters → "Not long enough" error
- Measurement Description: minimum 15 characters → "Not long enough" error

✅ **Hierarchical B-field UI:**
- "Require B field" checkbox with sub-menu
- X, Y, Z axis checkboxes
- If Z checked: parallel/perpendicular sub-menu

✅ **Machine Matching:**
- Filters by all requirements (temp, B-field, connections, daughterboard)
- Selects machine with lowest projected wait time
- Optical filtering disabled (form-only)

✅ **Rush Job System:**
- Rush job appeal checkbox
- Email notification to all admin users
- Admin queue management interface
- Up/down arrows for reordering
- Position number input for direct positioning

✅ **Duration Calculation:**
- Currently uses cooldown × 2 formula (as specified)
- Can be enhanced with more sophisticated calculation later

---

## 10. Testing Recommendations

### Test the Form:
```bash
python manage.py runserver
```
Navigate to `/submit/` and test:
- Title with < 3 characters (should show "Not long enough")
- Description with < 15 characters (should show "Not long enough")
- Hierarchical B-field checkbox UI
- Rush job checkbox

### Test Rush Job Workflow:
1. Submit a request with rush job checkbox enabled
2. Check console for email output (development mode)
3. Log in as admin user (set a user's `is_staff=True`)
4. Navigate to `/admin/rush-jobs/`
5. Test queue reordering with arrows and position input

### Create Admin User:
```bash
python manage.py createsuperuser
```

Or set existing user as staff:
```python
python manage.py shell
from django.contrib.auth.models import User
user = User.objects.get(username='your_username')
user.is_staff = True
user.save()
```

---

## 11. Future Enhancements

### Optical Capability Filtering:
To enable optical filtering in machine matching, uncomment and modify lines 174-176 in `calendarEditor/matching_algorithm.py`

### Duration Calculation:
Currently using `cooldown × 2`. To implement more sophisticated calculation:
1. Update form to calculate duration based on specific parameters
2. Modify `submit_queue_entry()` view to auto-calculate before saving

### Email in Production:
Update `mysite/settings.py` with SMTP credentials:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'your-email@gmail.com'
```

---

## 12. Files Modified

- `calendarEditor/models.py` - Added rush job fields
- `calendarEditor/forms.py` - Updated labels, validation, rush job field
- `calendarEditor/matching_algorithm.py` - Disabled optical filter, added reordering functions
- `calendarEditor/views.py` - Added rush job notification and admin views
- `calendarEditor/urls.py` - Added admin URL routes
- `templates/calendarEditor/submit_queue.html` - Hierarchical B-field UI
- `templates/calendarEditor/admin_rush_jobs.html` - New admin interface
- `mysite/settings.py` - Email configuration

## 13. New Files Created

- `calendarEditor/migrations/0004_queueentry_is_rush_job_and_more.py`
- `templates/calendarEditor/admin_rush_jobs.html`

---

**Implementation Complete!** ✅

All requirements have been implemented according to specifications. The system now supports:
- Enhanced form validation with custom error messages
- Hierarchical B-field checkbox UI
- Machine matching based on lowest projected wait
- Rush job appeal system with admin notifications
- Queue reordering interface for admins
