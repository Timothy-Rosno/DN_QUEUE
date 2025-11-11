# Testing Guide

This document provides information about the test suite for the scheduler application.

## Test Structure

The application includes comprehensive tests for all major components:

### calendarEditor Tests (`calendarEditor/tests/`)

- **test_models.py** - Model tests for Machine, QueueEntry, QueuePreset, Notification, NotificationPreference, and ScheduleEntry (legacy)
- **test_views.py** - View tests for public display, queue management, presets, and notifications
- **test_admin_views.py** - Admin interface tests for dashboard, user management, queue management, and rush jobs
- **test_matching_algorithm.py** - Machine matching algorithm tests including temperature, B-field, connections, and wait time calculations
- **test_notifications.py** - Notification system tests for creation, delivery, preferences, and WebSocket integration
- **test_websocket.py** - WebSocket consumer tests for real-time updates
- **test_api.py** - API endpoint tests for presets and notifications

### userRegistration Tests (`userRegistration/tests/`)

- **test_models.py** - UserProfile model tests including approval status and relationships
- **test_views.py** - Registration and profile management view tests
- **test_middleware.py** - User approval middleware tests

## Running Tests

### Run All Tests

```bash
python manage.py test
```

### Run Specific App Tests

```bash
# Test only calendarEditor
python manage.py test calendarEditor

# Test only userRegistration
python manage.py test userRegistration
```

### Run Specific Test File

```bash
# Test models only
python manage.py test calendarEditor.tests.test_models

# Test admin views
python manage.py test calendarEditor.tests.test_admin_views
```

### Run Specific Test Class or Method

```bash
# Test specific class
python manage.py test calendarEditor.tests.test_models.MachineModelTest

# Test specific method
python manage.py test calendarEditor.tests.test_models.MachineModelTest.test_machine_creation
```

### Run with Verbose Output

```bash
# Show test names as they run
python manage.py test --verbosity=2

# Show even more detail
python manage.py test --verbosity=3
```

### Run Tests in Parallel

```bash
# Run tests using multiple CPU cores
python manage.py test --parallel
```

### Keep Test Database

```bash
# Keep test database for faster subsequent runs
python manage.py test --keepdb
```

### Stop on First Failure

```bash
# Stop immediately when a test fails
python manage.py test --failfast
```

## Test Coverage

The test suite provides comprehensive coverage of:

### Models
- ✅ All model fields and relationships
- ✅ Model methods and properties
- ✅ Cascade deletions and constraints
- ✅ Auto-generated fields (timestamps, display names)

### Views
- ✅ Authentication and permissions
- ✅ Form validation and submission
- ✅ GET and POST request handling
- ✅ Redirect behavior
- ✅ Template rendering
- ✅ Context data

### Business Logic
- ✅ Machine matching algorithm (temperature, B-field, connections)
- ✅ Queue position management
- ✅ Wait time calculations
- ✅ Notification creation and delivery
- ✅ Preset permission checking

### API Endpoints
- ✅ JSON request/response handling
- ✅ Error handling
- ✅ Permission checks
- ✅ Data serialization

### Middleware
- ✅ User approval checking
- ✅ URL access control
- ✅ Staff/superuser bypass
- ✅ Profile auto-creation

### WebSocket
- ✅ Consumer connection/disconnection
- ✅ Message broadcasting
- ✅ User-specific notification channels

## Test Database

Tests use an in-memory SQLite database by default. The database is created fresh for each test run and destroyed afterward.

### Configuration

Test database settings are in `mysite/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

For tests, Django automatically creates a test database with the prefix `test_`.

## Writing New Tests

### Test Organization

1. Create test files in the appropriate `tests/` directory
2. Name test files with `test_` prefix (e.g., `test_models.py`)
3. Group related tests into test classes
4. Use descriptive test method names starting with `test_`

### Example Test Structure

```python
from django.test import TestCase
from django.contrib.auth.models import User

class MyModelTest(TestCase):
    """Test MyModel functionality."""

    def setUp(self):
        """Create test data that's used by multiple tests."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_model_creation(self):
        """Test that model can be created successfully."""
        # Test implementation
        pass

    def test_model_string_representation(self):
        """Test __str__ method."""
        # Test implementation
        pass
```

### Best Practices

1. **Isolation** - Each test should be independent and not rely on other tests
2. **Clear Names** - Test names should clearly describe what they test
3. **Arrange-Act-Assert** - Structure tests with setup, execution, and verification
4. **Coverage** - Test both success and failure cases
5. **Mocking** - Use mocks for external dependencies (WebSockets, channel layers)

### Using Mocks

For tests that interact with external services (e.g., WebSocket channel layer):

```python
from unittest.mock import patch, MagicMock

class NotificationTest(TestCase):
    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notification_creation(self, mock_channel_layer):
        """Test notification creation with mocked WebSocket."""
        mock_channel_layer.return_value = MagicMock()
        # Test implementation
```

## Continuous Integration

For CI/CD pipelines, use:

```bash
# Run all tests with coverage reporting
python manage.py test --verbosity=2 --failfast
```

## Test Statistics

As of the most recent run:

- **Total Tests**: 198
- **Test Files**: 10 (7 in calendarEditor, 3 in userRegistration)
- **Coverage Areas**:
  - Models: ~40 tests
  - Views: ~60 tests
  - Admin Views: ~25 tests
  - Matching Algorithm: ~30 tests
  - Notifications: ~20 tests
  - API Endpoints: ~15 tests
  - Middleware: ~8 tests

## Troubleshooting

### Common Issues

**Import Errors**
- Ensure you're running tests from the project root
- Check that all dependencies are installed

**Database Errors**
- Run migrations: `python manage.py migrate`
- Delete test database if corrupted: `rm test_*.db`

**WebSocket Tests Fail**
- Ensure Channels is properly installed
- Check that channel layers are configured in settings

**Middleware Tests Fail**
- Verify middleware is in MIDDLEWARE setting
- Check URL patterns are correctly configured

## Related Documentation

- [Django Testing Documentation](https://docs.djangoproject.com/en/4.2/topics/testing/)
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [LEGACY.md](./LEGACY.md) - Legacy code documentation

---

**Last Updated**: 2025-01-XX
**Test Framework**: Django 4.2.25 TestCase
**Test Runner**: Django default test runner
