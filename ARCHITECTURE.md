# Lab Equipment Queue Scheduler - Architecture Documentation

## Overview

This Django application manages a queue-based scheduling system for shared lab equipment (cryogenic refrigerators/"fridges"). Users submit job requests with specific requirements (temperature, magnetic field, connections, optical access), and the system automatically assigns them to compatible machines and manages the execution queue.

---

## System Architecture

### Technology Stack

- **Framework**: Django 4.2.25
- **Database**: SQLite (development), PostgreSQL-ready for production
- **Real-time Communication**: Django Channels + Redis
- **ASGI Server**: Daphne
- **Authentication**: Django's built-in auth system with custom user approval workflow

###Application Structure

```
schedulerTEST/
├── mysite/                  # Django project configuration
│   ├── settings.py         # Project settings
│   ├── urls.py             # Root URL configuration
│   ├── asgi.py             # ASGI application (WebSocket support)
│   └── wsgi.py             # WSGI application (HTTP)
│
├── calendarEditor/          # CORE APP - Queue & Machine Management
│   ├── models.py           # Machine, QueueEntry, QueuePreset, Notification models
│   ├── views.py            # Queue management, presets, legacy views
│   ├── admin_views.py      # Admin dashboard, user approval, queue management
│   ├── forms.py            # Django forms for queue entries and presets
│   ├── consumers.py        # WebSocket consumers for real-time updates
│   ├── routing.py          # WebSocket URL routing
│   ├── notifications.py    # Notification generation and delivery
│   ├── matching_algorithm.py  # Machine matching and queue ordering logic
│   ├── admin.py            # Django admin customization
│   ├── urls.py             # URL routing
│   └── management/commands/
│       ├── populate_machines.py    # Database seeding utility
│       ├── test_matching.py        # Matching algorithm test utility
│       └── runserver_with_redis.py # Development server helper
│
├── userRegistration/        # User Authentication & Approval
│   ├── models.py           # UserProfile model
│   ├── views.py            # Registration, email verification, profile
│   ├── forms.py            # Registration and profile forms
│   ├── middleware.py       # UserApprovalMiddleware
│   ├── admin.py            # Admin customization
│   └── urls.py             # URL routing
│
└── templates/               # Django templates
    ├── base.html           # Base template with navigation & notification bell
    ├── registration/       # Django auth templates
    ├── userRegistration/   # User registration templates
    └── calendarEditor/
        ├── public/         # Public display pages
        ├── admin/          # Admin interface templates
        └── legacy/         # Deprecated templates (scheduled for removal)
```

---

## Core Components

### 1. Queue Management System

#### Machine Matching Algorithm (`matching_algorithm.py`)

**Purpose**: Automatically assigns user requests to compatible lab equipment

**Algorithm Flow**:
1. Filter machines by temperature requirements
2. Filter by magnetic field strength requirements
3. Filter by magnetic field direction requirements
4. Filter by DC/RF line requirements
5. Filter by daughterboard compatibility
6. Filter by optical capabilities
7. Select machine with **shortest wait time** (earliest availability)

**Key Functions**:
- `find_best_machine(queue_entry)` - Returns optimal machine or None
- `assign_to_queue(queue_entry, machine)` - Assigns entry to machine queue
- `reorder_queue(machine)` - Reorders queue after cancellations
- `move_queue_entry_up/down(entry_id)` - Admin queue manipulation
- `set_queue_position(entry_id, position)` - Direct position assignment

#### Queue Position Tracking

- Each `QueueEntry` has a `queue_position` field (1-indexed)
- Position determines execution order on the assigned machine
- **Position #1 = "ON DECK"** - triggers special notification
- Automatic reordering when entries are cancelled or completed

#### Wait Time Estimation

**Machine Level**:
```python
Machine.get_estimated_wait_time()
```
- Sums duration of all queued entries + cooldown times
- Returns total wait in hours

**Entry Level**:
```python
QueueEntry.calculate_estimated_start_time()
```
- Calculates when this specific entry will start
- Accounts for all entries ahead in queue
- Includes machine cooldown periods
- Returns datetime of estimated start

---

### 2. Preset System

**Purpose**: Save and share common experiment configurations

**Features**:
- **Private Presets**: Only visible/editable by creator
- **Public Presets**: Visible to all, editable by admins
- **Auto-fill**: Load preset to populate queue submission form
- **Copy**: Duplicate existing presets as templates
- **Edit Tracking**: `last_edited_by` and `last_edited_at` fields

**Permission Model**:
```python
QueuePreset.can_edit(user)
```
- Creators can edit their own presets (public or private)
- Admins can edit any public preset
- Non-admins cannot edit others' presets

---

### 3. Real-time Notification System

#### Architecture

**WebSocket Layer**: Django Channels + Redis
- Users connect to WebSocket at `/ws/queue-updates/`
- Each user joins global `queue_updates` group
- Each user joins personal `user_{id}_notifications` group

**Notification Types**:
1. **Preset Notifications**:
   - `preset_created` - New public preset available
   - `preset_edited` - Public preset modified
   - `preset_deleted` - Preset removed

2. **Queue Notifications**:
   - `queue_added` - Entry added to machine queue
   - `queue_moved` - Queue position changed
   - `queue_cancelled` - Entry cancelled
   - `on_deck` - **YOU'RE NEXT!** (Position #1)
   - `job_started` - Your job is running
   - `job_completed` - Your job finished

#### Notification Delivery Flow

```
Action (e.g., preset created)
    ↓
notifications.notify_preset_created()
    ↓
Create Notification in database
    ↓
Send to WebSocket channel_layer
    ↓
QueueUpdatesConsumer receives event
    ↓
Broadcast to user's WebSocket connection
    ↓
JavaScript updates UI (bell badge, dropdown)
    ↓
Optional: Browser desktop notification
```

#### User Preferences

Users can configure which notifications they receive via `NotificationPreference` model:
- In-app notifications (bell icon)
- Email notifications (future)
- Granular control per notification type

---

### 4. User Management

#### Registration Flow

1. **User Registration** (`/user/register/`)
   - User fills out registration form
   - Email verification code sent
   - Account created but not approved

2. **Email Verification** (`/user/verify/<code>/`)
   - User clicks link in email
   - Email verified

3. **Admin Approval** (`/schedule/admin-users/`)
   - Admins see pending users
   - Approve or reject with notes
   - Approved users can access the system

4. **Middleware Protection**
   - `UserApprovalMiddleware` checks approval status
   - Unapproved users redirected to pending page
   - Ensures only approved users can submit queue entries

#### User Profile

- Extended via `UserProfile` model (OneToOne with User)
- Fields: phone, department, notes, approval status
- Linked to `NotificationPreference` for notification settings

---

### 5. Admin Dashboard

Unified admin interface in `admin_views.py`:

**Dashboard** (`/schedule/admin-dashboard/`)
- System overview
- Quick stats (pending users, rush jobs, total queue)
- Links to all admin functions

**User Management** (`/schedule/admin-users/`)
- Approve/reject pending users
- View all users
- Delete users

**Machine Management** (`/schedule/admin-machines/`)
- View all machines
- Edit machine specifications
- Check queue status per machine

**Queue Management** (`/schedule/admin-queue/`)
- View all queue entries by machine
- Reorder queue (move up/down, set position)
- Reassign entries to different machines

**Rush Job Management** (`/schedule/admin-rush-jobs-review/`)
- Review rush job appeals
- Approve rush job (moves to position #1)
- Reject rush job appeal

---

## Data Models

### Machine

Represents lab equipment with capabilities:

**Specifications**:
- Temperature range (`min_temp`, `max_temp` in Kelvin)
- Magnetic field strengths (`b_field_x`, `b_field_y`, `b_field_z` in Tesla)
- Magnetic field directions (parallel/perpendicular/both/none)
- Connection types (`dc_lines`, `rf_lines` counts)
- Daughterboard compatibility (e.g., "QBoard I", "Montana Puck")
- Optical capabilities (none/available/with_work/under_construction)

**Operational Status**:
- Current status (idle/running/cooldown/maintenance)
- Current user (if running)
- Estimated available time
- Cooldown period between jobs

### QueueEntry

User's job request in the queue:

**Requirements** (used for matching):
- Temperature requirements
- Magnetic field requirements
- Connection requirements
- Optical requirements
- Estimated duration

**Queue Management**:
- `assigned_machine` - Machine assigned by matching algorithm
- `queue_position` - Position in machine's queue (1 = ON DECK)
- `status` - queued/running/completed/cancelled
- `priority` - Normal or admin-adjusted priority
- `is_rush_job` - Rush job flag

**Timestamps**:
- `submitted_at` - When request was submitted
- `estimated_start_time` - Calculated start time
- `started_at` - When job started running
- `completed_at` - When job finished

### QueuePreset

Saved configuration template:

**Identity**:
- `name` - Internal identifier (auto-generated)
- `display_name` - User-facing name
- `is_public` - Visibility flag

**Ownership**:
- `creator` - User who created it
- `last_edited_by` - User who last modified it
- `last_edited_at` - Modification timestamp

**Configuration**: Same requirement fields as QueueEntry

### Notification

In-app notification record:

- `recipient` - User receiving notification
- `notification_type` - Type enum (see notification types above)
- `title` - Short notification title
- `message` - Detailed message
- `related_preset` / `related_queue_entry` / `related_machine` - Context objects
- `triggering_user` - User who caused the notification
- `is_read` - Read status
- `created_at` - Timestamp

### NotificationPreference

User's notification settings:

**Preset Notifications**:
- `notify_public_preset_created/edited/deleted`
- `notify_private_preset_edited`

**Queue Notifications**:
- `notify_queue_position_change`
- `notify_on_deck` ⭐
- `notify_job_started`
- `notify_job_completed`
- `notify_machine_queue_changes`

**Delivery Channels**:
- `in_app_notifications` - Bell icon (active)
- `email_notifications` - Email delivery (infrastructure ready)

---

## URL Routing Map

### Public Routes

| URL | View | Purpose |
|-----|------|---------|
| `/` | `calendarEditor.views.home` | Public machine status dashboard |
| `/login/` | Django auth | User login |
| `/logout/` | Django auth | User logout |

### User Routes (`/user/`)

| URL | View | Purpose |
|-----|------|---------|
| `/user/register/` | `register` | User registration |
| `/user/verify/<code>/` | `email_verification` | Email verification |
| `/user/profile/` | `profile` | User profile management |

### Queue Routes (`/schedule/`)

| URL | View | Purpose |
|-----|------|---------|
| `/schedule/submit/` | `submit_queue_entry` | Submit new queue request |
| `/schedule/my-queue/` | `my_queue` | View your queue entries |
| `/schedule/cancel/<pk>/` | `cancel_queue_entry` | Cancel queued entry |

### Preset Routes (`/schedule/preset/`)

| URL | View | Purpose |
|-----|------|---------|
| `/schedule/preset/create/` | `create_preset` | Create new preset |
| `/schedule/preset/edit/<id>/` | `edit_preset_view` | Edit existing preset |
| `/schedule/preset/copy/<id>/` | `copy_preset` | Duplicate preset |
| `/schedule/preset/delete/<id>/` | `delete_preset` | Delete preset |
| `/schedule/api/preset/<id>/` | `load_preset_ajax` | Load preset data (AJAX) |
| `/schedule/api/presets/editable/` | `get_editable_presets_ajax` | Get editable presets (AJAX) |
| `/schedule/api/presets/viewable/` | `get_viewable_presets_ajax` | Get viewable presets (AJAX) |

### Admin Routes (`/schedule/admin-*`)

| URL | View | Purpose |
|-----|------|---------|
| `/schedule/admin-dashboard/` | `admin_dashboard` | Admin home |
| `/schedule/admin-users/` | `admin_users` | User management |
| `/schedule/admin-machines/` | `admin_machines` | Machine management |
| `/schedule/admin-queue/` | `admin_queue` | Queue overview |
| `/schedule/admin-rush-jobs-review/` | `admin_rush_jobs` | Rush job appeals |
| `/schedule/admin-queue/move-up/<id>/` | `move_queue_up` | Move entry up in queue |
| `/schedule/admin-queue/move-down/<id>/` | `move_queue_down` | Move entry down in queue |
| `/schedule/admin-queue/reassign/<id>/` | `reassign_machine` | Reassign to different machine |
| `/schedule/admin-rush-jobs/approve/<id>/` | `approve_rush_job` | Approve rush job appeal |
| `/schedule/admin-rush-jobs/reject/<id>/` | `reject_rush_job` | Reject rush job appeal |

### Notification API (`/schedule/notifications/api/`)

| URL | View | Purpose |
|-----|------|---------|
| `/schedule/notifications/api/list/` | `notification_list_api` | Get notifications (JSON) |
| `/schedule/notifications/api/mark-read/` | `notification_mark_read_api` | Mark notification read (POST) |
| `/schedule/notifications/api/mark-all-read/` | `notification_mark_all_read_api` | Mark all read (POST) |

### WebSocket

| URL | Consumer | Purpose |
|-----|----------|---------|
| `/ws/queue-updates/` | `QueueUpdatesConsumer` | Real-time updates channel |

---

## Security & Permissions

### Authentication

- All queue/preset operations require login (`@login_required`)
- Admin functions require staff status (`@user_passes_test(is_staff)`)
- Email verification required for account activation
- Admin approval required before accessing queue system

### Authorization

**Preset Permissions**:
```python
def can_edit(preset, user):
    if user == preset.creator:
        return True  # Creator can edit
    if user.is_staff and preset.is_public:
        return True  # Admins can edit public presets
    return False
```

**Queue Entry Permissions**:
- Users can only view/cancel their own entries
- Admins can view/manage all entries
- Machine assignment is automatic (no user override)

**Admin Functions**:
- User approval/rejection: Staff only
- Queue reordering: Staff only
- Rush job approval: Staff only
- Machine editing: Staff only

### Middleware

**UserApprovalMiddleware**:
- Intercepts all requests from authenticated users
- Checks `UserProfile.is_approved` status
- Redirects unapproved users to pending page
- Allows access to logout and pending status pages

---

## Development Utilities

### Management Commands

**populate_machines.py**:
```bash
python manage.py populate_machines
```
- Seeds database with sample machines
- Useful for development/testing
- Creates realistic machine specifications

**test_matching.py**:
```bash
python manage.py test_matching
```
- Tests the matching algorithm
- Creates sample queue entries
- Shows matching results and reasoning

**runserver_with_redis.py**:
```bash
python manage.py runserver_with_redis
```
- Starts Redis server (if installed)
- Starts Django development server
- Ensures WebSocket support is available

---

## WebSocket Architecture

### Connection Flow

```
Client (JavaScript)
    ↓
new WebSocket('ws://host/ws/queue-updates/')
    ↓
QueueUpdatesConsumer.connect()
    ↓
Add to 'queue_updates' group (global)
Add to 'user_123_notifications' group (personal)
    ↓
Accept connection
    ↓
Listen for messages from channel layer
    ↓
Forward messages to client
```

### Message Types

**Preset Updates** (`message_type: 'preset_update'`):
```json
{
  "message_type": "preset_update",
  "update_type": "created" | "edited" | "deleted",
  "preset_id": 123,
  "preset_data": {...}
}
```

**Queue Updates** (`message_type: 'queue_update'`):
```json
{
  "message_type": "queue_update",
  "update_type": "submitted" | "cancelled" | "moved",
  "entry_id": 456,
  "user_id": 789,
  "machine_id": 12
}
```

**Notifications** (`message_type: 'notification'`):
```json
{
  "message_type": "notification",
  "notification_id": 99,
  "notification_type": "on_deck",
  "title": "🎯 ON DECK - You're Next!",
  "message": "Your request is now #1...",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Channel Layer Configuration

**Backend**: Redis
**Host**: localhost:6379 (development)
**Groups**:
- `queue_updates` - Global updates (all users)
- `user_{id}_notifications` - Personal notifications (per user)

---

## Deployment Considerations

### Environment Variables

- `SECRET_KEY` - Django secret key (must be unique in production)
- `DEBUG` - Set to False in production
- `ALLOWED_HOSTS` - Add production domains
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string for Channels

### Database Migration

SQLite (development) → PostgreSQL (production):
1. Export data: `python manage.py dumpdata > data.json`
2. Update `DATABASES` in settings.py
3. Run migrations: `python manage.py migrate`
4. Import data: `python manage.py loaddata data.json`

### Static Files

```bash
python manage.py collectstatic
```
- Collects all static files to STATIC_ROOT
- Serve via nginx/Apache in production

### WebSocket Deployment

Requires ASGI server (Daphne, uvicorn, or hypercorn):
```bash
daphne -b 0.0.0.0 -p 8000 mysite.asgi:application
```

### Redis Configuration

Production Redis should:
- Run as a service (systemd, Docker, etc.)
- Use authentication (requirepass)
- Configure persistence (RDB or AOF)
- Set max memory limits

---

## Testing Strategy

See `tests/` directories for comprehensive test coverage:

- **Model Tests**: Field validation, methods, relationships
- **View Tests**: Form submission, redirects, permissions
- **Algorithm Tests**: Machine matching logic, edge cases
- **WebSocket Tests**: Consumer connections, message broadcasting
- **API Tests**: JSON responses, authentication, error handling
- **Integration Tests**: End-to-end workflows

---

## Future Enhancements

- [ ] Email notification delivery (infrastructure ready)
- [ ] Slack integration for notifications
- [ ] SMS notifications for ON DECK status
- [ ] Calendar export (iCal format)
- [ ] Machine utilization analytics
- [ ] Automated job completion detection
- [ ] Multi-machine job support
- [ ] Job dependencies (one job waits for another)
- [ ] Recurring job templates

---

## Maintenance

### Regular Tasks

- Monitor Redis memory usage
- Archive completed QueueEntry records (>6 months old)
- Clean up unverified UserProfile records (>7 days old)
- Review and remove legacy code (see LEGACY.md)

### Monitoring

Key metrics to track:
- Average queue wait time per machine
- Machine utilization rate
- User registration → approval time
- WebSocket connection failures
- Rush job approval rate

---

**Version**: 1.0
**Last Updated**: 2025-01-XX
**Maintainers**: Lab Equipment Queue Team
