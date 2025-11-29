# Legacy Code Documentation

This document tracks legacy code in the scheduler application that is scheduled for removal in future versions.

## Overview

The application has evolved from a simple scheduling system (`ScheduleEntry` model) to a sophisticated queue management system (`QueueEntry` model). This document tracks the old code that remains for backwards compatibility.

---

## Legacy Schedule System

### **Status**: Deprecated - Scheduled for removal in v2.0

### Models

#### ScheduleEntry (`calendarEditor/models.py`)
- **Location**: Lines 296-326
- **Purpose**: Old scheduling model before the queue system was implemented
- **Status**: Model kept for migration compatibility
- **Data**: Check if any ScheduleEntry records exist in the database before deletion
- **Removal Plan**: Migrate any existing data to QueueEntry format, then remove model and migrations

### Views (`calendarEditor/views.py`)

#### schedule_list() - Line 262
- **Route**: `/schedule/schedule/`
- **Template**: `templates/calendarEditor/legacy/schedule_list.html`
- **Purpose**: Lists user's upcoming and past schedule entries
- **Replacement**: Use `/schedule/my-queue/` (QueueEntry system)

#### create_schedule() - Line 287
- **Route**: `/schedule/create/`
- **Template**: `templates/calendarEditor/legacy/create_schedule.html`
- **Purpose**: Create schedule entries using old ScheduleEntry model
- **Replacement**: Use `/schedule/submit/` (Queue submission)

#### edit_schedule() - Line 304
- **Route**: `/schedule/edit/<pk>/`
- **Template**: `templates/calendarEditor/legacy/edit_schedule.html`
- **Purpose**: Edit schedule entries
- **Replacement**: Queue entries cannot be edited after submission (by design)

#### delete_schedule() - Line 324
- **Route**: `/schedule/delete/<pk>/`
- **Template**: `templates/calendarEditor/legacy/delete_schedule.html`
- **Purpose**: Delete schedule entries
- **Replacement**: Use `/schedule/cancel/<pk>/` (Cancel queue entry)

#### welcome_page() - Line 283
- **Route**: **NONE** (Orphaned view - no route defined)
- **Template**: `templates/calendarEditor/legacy/welcome_page.html`
- **Purpose**: Unknown - appears to be an abandoned welcome page
- **Replacement**: Home page at `/`
- **Action**: Safe to delete immediately - no route exists

---

## Legacy Admin Views

### **Status**: Duplicated by admin_views.py - Scheduled for removal in v2.0

These views have been superseded by newer implementations in `admin_views.py`. They're kept temporarily for backwards compatibility with any external links.

### Views (`calendarEditor/views.py`)

#### admin_rush_jobs() - Line 414
- **Route**: `/schedule/admin/rush-jobs/`
- **Template**: `templates/calendarEditor/legacy/admin_rush_jobs.html`
- **Purpose**: Old admin interface for managing rush job requests
- **Replacement**: `/schedule/admin-rush-jobs-review/` (admin_views.admin_rush_jobs)
- **New Template**: `templates/calendarEditor/admin/admin_rush_jobs.html`

#### admin_move_queue_entry() - Line 453
- **Route**: `/schedule/admin/move/<entry_id>/<direction>/`
- **Purpose**: Move queue entries up/down
- **Replacement**:
  - `/schedule/admin-queue/move-up/<entry_id>/` (admin_views.move_queue_up)
  - `/schedule/admin-queue/move-down/<entry_id>/` (admin_views.move_queue_down)

#### admin_set_queue_position() - Line 501
- **Route**: `/schedule/admin/set-position/<entry_id>/`
- **Purpose**: Set queue entry to specific position
- **Replacement**: Admin queue management in `/schedule/admin-queue/`

---

## Merged Apps

### calendarDisplay App

**Status**: ✅ MERGED into calendarEditor (Completed)

The `calendarDisplay` app had no models of its own and only contained 2 public display views. It has been successfully merged into `calendarEditor`:

- **home()** view: Now at root `/` (mysite/urls.py line 25)
  - Template moved from `calendarDisplay/home.html` to `calendarEditor/public/home.html`
- **schedule_list()** view: Now marked as LEGACY (see above)
  - Template moved from `calendarDisplay/schedule_list.html` to `calendarEditor/legacy/schedule_list.html`

The app directory and all references have been removed from:
- `mysite/settings.py` (removed from INSTALLED_APPS)
- `mysite/urls.py` (routes now point directly to calendarEditor views)
- File system (`calendarDisplay/` directory deleted)

---

## Migration Path

### For ScheduleEntry → QueueEntry Migration

If you have existing ScheduleEntry data that needs to be preserved:

1. **Export existing ScheduleEntry data**:
   ```python
   python manage.py shell
   from calendarEditor.models import ScheduleEntry
   entries = ScheduleEntry.objects.all()
   # Export to JSON or analyze data
   ```

2. **Create migration script** to convert ScheduleEntry → QueueEntry:
   - Map `start_datetime` → queue submission time
   - Map `estimated_duration` → `estimated_duration_hours`
   - Assign to appropriate machine based on requirements
   - Set initial queue position

3. **Verify migration**:
   - Confirm all data transferred
   - Test queue functionality
   - Check user access to migrated entries

4. **Remove legacy code**:
   - Delete legacy views
   - Delete legacy templates
   - Delete legacy URL routes
   - Delete ScheduleEntry model
   - Create new migration to remove ScheduleEntry table

---

## Removal Checklist

Before removing legacy code in v2.0:

### Pre-Removal Tasks:
- [ ] Verify no ScheduleEntry records exist in database
- [ ] Confirm no external bookmarks/links use legacy URLs
- [ ] Notify users of deprecated routes
- [ ] Update any documentation referencing old routes
- [ ] Check server logs for legacy route usage

### Removal Steps:
1. Delete legacy view functions from `views.py`
2. Delete legacy URL patterns from `urls.py`
3. Delete `templates/calendarEditor/legacy/` directory
4. Remove ScheduleEntry model from `models.py`
5. Create migration to drop ScheduleEntry table
6. Remove this LEGACY.md file

---

## URL Route Comparison

### Old Routes (Legacy) → New Routes (Active)

| Legacy Route | New Route | Status |
|-------------|-----------|--------|
| `/schedule/` | `/schedule/my-queue/` | Active |
| `/schedule/create/` | `/schedule/submit/` | Active |
| `/schedule/edit/<pk>/` | N/A (no editing by design) | - |
| `/schedule/delete/<pk>/` | `/schedule/cancel/<pk>/` | Active |
| `/schedule/admin/rush-jobs/` | `/schedule/admin-rush-jobs-review/` | Active |
| `/schedule/admin/move/<id>/<dir>/` | `/schedule/admin-queue/move-up/<id>/`<br>`/schedule/admin-queue/move-down/<id>/` | Active |
| `/schedule/admin/set-position/<id>/` | Admin Queue Management | Active |

---

## Contact

For questions about legacy code removal or migration:
- Check git history for context on why code was deprecated
- Review GitHub issues for related discussions
- Contact maintainers before removing any legacy code

---

**Last Updated**: 2025-01-XX
**Target Removal Version**: v2.0
**Estimated Removal Date**: TBD
