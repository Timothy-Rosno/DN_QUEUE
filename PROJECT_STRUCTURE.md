# Project Structure

This document explains the organization of the Lab Equipment Queue Scheduler codebase.

## 📁 Directory Structure

```
schedulerTEST/
├── calendarEditor/          # Main Django app (queue management, notifications, etc.)
├── userRegistration/        # User authentication and profile management
├── mysite/                  # Django project settings
├── temperature_gateway/     # Temperature monitoring gateway script
├── templates/               # HTML templates
├── static/                  # Static files (CSS, JS, images)
├── old_tests/              # Archived test scripts
├── useless_files/          # Unrelated experimental code
├── old_todo_and_done/      # Historical documentation
└── [Setup Guides]          # Active documentation (see below)
```

## 📚 Setup Guides (Root Directory)

Essential documentation for setting up and maintaining the system:

- **ARCHITECTURE.md** - System architecture overview
- **DATABASE_BACKUP.md** - Backup and restore procedures
- **GITHUB_ACTIONS_SETUP.md** - GitHub Actions configuration
- **NETWORK_LIMITATIONS.md** - Network constraints and workarounds
- **PUSH_TO_GITHUB.md** - GitHub push instructions
- **QUEUE_SYSTEM_INSTALLATION_GUIDE.md** - Complete installation guide
- **QUICK_START.md** - Quick deployment guide
- **RENDER_DEPLOYMENT_GUIDE.md** - Render.com deployment
- **SLACK_SETUP.md** - Slack integration setup

## 📦 Archived Folders

### old_tests/
Old test scripts and diagnostic tools that are no longer actively used:
- Test scripts for notifications, reminders, secure links
- Slack diagnostic tools
- One-time fix scripts
- WebSocket testing

### useless_files/
Unrelated experimental code:
- Statistical correlation experiments
- Temperature retrieval experiments
- IP address utilities
- Homework/experimental code

### old_todo_and_done/
Historical documentation and completed tasks:
- Bug fix summaries
- Implementation notes
- Testing checklists
- Old TODO lists
- Security update documentation
- Legacy system notes

## 🔧 Essential Files

- **manage.py** - Django management script
- **requirements.txt** - Python dependencies
- **runtime.txt** - Python version specification
- **initial_data.json** - Initial database fixtures
- **CryoCore.py** - CryoCore equipment interface
- **OptiCool.py** - OptiCool equipment interface
- **runserver.py** - Development server launcher
- **start.sh** - Production server starter
- **fix-render-commands.sh** - Render.com command fixes

## 🧪 Active Tests

The proper test suite is located in `calendarEditor/tests/`:
- `test_models.py`
- `test_views.py`
- `test_notifications.py`
- `test_admin_views.py`
- `test_matching_algorithm.py`
- `test_middleware.py`

Run tests with: `python manage.py test`

## 📝 Git History

All archived files were moved, not deleted, so their full history is preserved in git:
```bash
# To see the history of a moved file:
git log --follow old_tests/test_slack.py

# To restore an old file:
git checkout HEAD -- old_tests/test_slack.py
cp old_tests/test_slack.py .
```

## 🗑️ Safe to Delete?

The archived folders (`old_tests/`, `useless_files/`, `old_todo_and_done/`) can be safely deleted if you're confident you won't need them for reference. However, they're kept for now as they may contain useful debugging information or historical context.

If you want to delete them:
```bash
rm -rf old_tests useless_files old_todo_and_done
git add -A
git commit -m "Remove archived folders"
```

---

*Last updated: November 2025*
*Organized by: Advanced Intern™*
