# Legacy Template Archive

This directory contains legacy templates from the old ScheduleEntry system that has been replaced by the QueueEntry system.

## Contents

- `schedule_list.html` - Old schedule list view
- `create_schedule.html` - Old schedule creation form
- `edit_schedule.html` - Old schedule edit form
- `delete_schedule.html` - Old schedule deletion confirmation
- `welcome_page.html` - Orphaned welcome page (no route defined)
- `admin_rush_jobs.html` - Old admin rush jobs view (replaced by new admin interface)

## Status

These templates are **DEPRECATED** and marked for removal in v2.0.

The legacy views that use these templates are still present in `calendarEditor/views.py` for backwards compatibility, but the routes are marked as LEGACY in `calendarEditor/urls.py`.

## Migration Path

All functionality from these templates has been migrated to the new QueueEntry-based system:
- Schedule management → Queue management (`submit_queue.html`, `my_queue.html`)
- Admin rush jobs → New admin interface (`admin/admin_rush_jobs.html`)

## Removal Plan

**Target:** Version 2.0
**Prerequisites:**
1. Verify no active users are accessing legacy routes (check server logs)
2. Migrate any remaining ScheduleEntry data to QueueEntry format
3. Remove legacy views from `views.py`
4. Remove legacy routes from `urls.py`
5. Delete this archive directory

---

**Date Archived:** October 28, 2025
**Archived By:** Phase 6.1 Implementation
