# Legacy Test Code Archive

This directory serves as documentation for legacy test code that should be removed in v2.0.

## Legacy Test Classes and Functions

The following test code in the parent `tests/` directory tests the old ScheduleEntry system and should be removed when the legacy views are removed:

### In `test_models.py`:
- `ScheduleEntryModelTest` class (entire class)
  - Tests the deprecated ScheduleEntry model
  - Tests legacy fields and methods

### In `test_views.py`:
- `LegacyScheduleViewsTest` class (if exists) or individual test methods:
  - `test_legacy_schedule_list_requires_login()`
  - `test_legacy_schedule_list_accessible()`
  - `test_legacy_create_schedule_get()`
  - Any other tests that reference `schedule`, `create_schedule`, `edit_schedule`, or `delete_schedule` views

## Status

These tests are for **DEPRECATED** functionality but are kept to ensure backwards compatibility until v2.0.

The tests verify functionality of:
- ScheduleEntry model (replaced by QueueEntry)
- Legacy schedule views (schedule_list, create_schedule, edit_schedule, delete_schedule)

## Removal Plan

**Target:** Version 2.0
**Steps:**
1. Remove legacy views from `views.py`
2. Remove legacy routes from `urls.py`
3. Remove legacy templates from `templates/legacy_archive/`
4. Remove the test classes/methods listed above
5. Remove ScheduleEntry model (after data migration)
6. Delete this archive directory

## Migration Path

Equivalent test coverage exists for the new QueueEntry system:
- `QueueEntryModelTest` - Tests QueueEntry model
- `QueueViewsTest` - Tests queue submission and management views
- `AdminQueueViewsTest` - Tests admin queue management

---

**Date Archived:** October 28, 2025
**Archived By:** Phase 6.1 Implementation
