from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    # Public pages
    path('fridges/', views.fridge_list, name='fridge_list'),
    path('queue/', views.public_queue, name='public_queue'),

    # New queue-based paths
    path('submit/', views.submit_queue_entry, name='submit_queue'),
    path('my-queue/', views.my_queue, name='my_queue'),
    path('cancel/<int:pk>/', views.cancel_queue_entry, name='cancel_queue'),
    path('appeal/<int:pk>/', views.appeal_queue_entry, name='appeal_queue'),

    # Check-in/Check-out paths (user self-service)
    path('check-in/<int:entry_id>/', views.check_in_job, name='check_in_job'),
    path('check-out/<int:entry_id>/', views.check_out_job, name='check_out_job'),
    path('undo-check-in/<int:entry_id>/', views.undo_check_in, name='undo_check_in'),
    path('snooze-reminder/<int:entry_id>/', views.snooze_checkout_reminder, name='snooze_checkout_reminder'),
    path('snooze-checkin-reminder/<int:entry_id>/', views.snooze_checkin_reminder, name='snooze_checkin_reminder'),
    path('check-in-check-out/', views.check_in_check_out, name='check_in_check_out'),

    # Preset management paths
    path('preset/create/', views.create_preset, name='create_preset'),
    path('preset/edit/<int:preset_id>/', views.edit_preset_view, name='edit_preset'),
    path('preset/view/<int:preset_id>/', views.view_preset, name='view_preset'),
    path('preset/copy/<int:preset_id>/', views.copy_preset, name='copy_preset'),
    path('api/preset/<int:preset_id>/', views.load_preset_ajax, name='load_preset'),
    path('api/presets/editable/', views.get_editable_presets_ajax, name='get_editable_presets'),
    path('api/presets/viewable/', views.get_viewable_presets_ajax, name='get_viewable_presets'),
    path('preset/delete/<int:preset_id>/', views.delete_preset, name='delete_preset'),
    path('preset/<int:preset_id>/follow/', views.follow_preset, name='follow_preset'),
    path('preset/<int:preset_id>/unfollow/', views.unfollow_preset, name='unfollow_preset'),

    # Custom Admin Interface
    path('admin-dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin-users/', admin_views.admin_users, name='admin_users'),
    path('admin-users/approve/<int:user_id>/', admin_views.approve_user, name='approve_user'),
    path('admin-users/reject/<int:user_id>/', admin_views.reject_user, name='reject_user'),
    path('admin-users/delete/<int:user_id>/', admin_views.delete_user, name='delete_user'),
    path('admin-users/promote/<int:user_id>/', admin_views.promote_to_staff, name='promote_to_staff'),
    path('admin-users/demote/<int:user_id>/', admin_views.demote_from_staff, name='demote_from_staff'),
    path('admin-users/edit-user-info/', admin_views.admin_edit_user_info, name='admin_edit_user_info'),
    path('admin-users/edit-user-info/<int:user_id>/', admin_views.admin_edit_user_info, name='admin_edit_user_info_with_id'),
    path('admin-machines/', admin_views.admin_machines, name='admin_machines'),
    path('admin-machines/add/', admin_views.add_machine, name='add_machine'),
    path('admin-machines/edit/<int:machine_id>/', admin_views.edit_machine, name='edit_machine'),
    path('admin-machines/delete/<int:machine_id>/', admin_views.delete_machine, name='delete_machine'),
    path('admin-queue/', admin_views.admin_queue, name='admin_queue'),
    path('admin-queue/edit/<int:entry_id>/', admin_views.admin_edit_entry, name='admin_edit_entry'),
    path('admin-queue/cancel/<int:entry_id>/', admin_views.admin_cancel_entry, name='admin_cancel_entry'),
    path('admin-rush-jobs-review/', admin_views.admin_rush_jobs, name='admin_rush_jobs'),
    path('admin-presets/', admin_views.admin_presets, name='admin_presets'),

    # Storage & Database Management
    path('admin/storage-stats/', admin_views.admin_storage_stats, name='admin_storage_stats'),
    path('admin/render-usage-stats/', admin_views.admin_render_usage_stats, name='admin_render_usage_stats'),
    path('admin/render-usage/', admin_views.admin_render_usage, name='admin_render_usage'),
    path('admin/database-management/', admin_views.admin_database_management, name='admin_database_management'),
    path('admin/export-archive/', admin_views.admin_export_archive, name='admin_export_archive'),
    path('admin/export-full-database/', admin_views.admin_export_full_database, name='admin_export_full_database'),
    path('admin/import-database/', admin_views.admin_import_database, name='admin_import_database'),
    path('admin/clear-archive-with-backup/', admin_views.admin_clear_archive_with_backup, name='admin_clear_archive_with_backup'),
    path('admin/clear-archive/', admin_views.admin_clear_archive, name='admin_clear_archive'),

    # API endpoint for automated backups (GitHub Actions)
    path('api/backup/database/', admin_views.api_export_database_backup, name='api_export_database_backup'),

    # GitHub cloud backups
    path('admin/github-backups/', admin_views.admin_list_github_backups, name='admin_list_github_backups'),
    path('admin/github-backups/download/<str:filename>/', admin_views.admin_download_github_backup, name='admin_download_github_backup'),
    path('admin/github-backups/restore/<str:filename>/', admin_views.admin_restore_github_backup, name='admin_restore_github_backup'),

    # Backwards compatibility aliases
    path('admin/archive-management/', admin_views.admin_archive_management, name='admin_archive_management'),

    # Queue Management Actions
    path('admin-queue/queue-next/<int:entry_id>/', admin_views.queue_next, name='queue_next'),
    path('admin-queue/move-up/<int:entry_id>/', admin_views.move_queue_up, name='move_queue_up'),
    path('admin-queue/move-down/<int:entry_id>/', admin_views.move_queue_down, name='move_queue_down'),
    path('admin-queue/reassign/<int:entry_id>/', admin_views.reassign_machine, name='reassign_machine'),

    # Admin Check-in/Check-out (admin can start/complete any user's job)
    path('admin-queue/check-in/<int:entry_id>/', admin_views.admin_check_in, name='admin_check_in'),
    path('admin-queue/check-out/<int:entry_id>/', admin_views.admin_check_out, name='admin_check_out'),
    path('admin-queue/undo-check-in/<int:entry_id>/', admin_views.admin_undo_check_in, name='admin_undo_check_in'),

    # Rush Job/Special Request Actions
    path('admin-rush-jobs/approve/<int:entry_id>/', admin_views.approve_rush_job, name='approve_rush_job'),
    path('admin-rush-jobs/reject/<int:entry_id>/', admin_views.reject_rush_job, name='reject_rush_job'),

    # Admin rush job management paths (existing)
    path('admin/rush-jobs/', views.admin_rush_jobs, name='admin_rush_jobs_old'),
    path('admin/move/<int:entry_id>/<str:direction>/', views.admin_move_queue_entry, name='admin_move_queue'),
    path('admin/set-position/<int:entry_id>/', views.admin_set_queue_position, name='admin_set_position'),

    # Archive paths
    path('archive/', views.archive_list, name='archive_list'),
    path('archive/create/', views.archive_create, name='archive_create'),
    path('archive/export-my-measurements/', views.export_my_measurements, name='export_my_measurements'),
    path('archive/save/<int:queue_entry_id>/', views.save_to_archive, name='save_to_archive'),
    path('archive/download/<int:archive_id>/', views.download_archive_file, name='download_archive_file'),
    path('archive/delete/<int:archive_id>/', views.delete_archive, name='delete_archive'),
    path('archive/bulk-delete/', views.bulk_delete_archives, name='bulk_delete_archives'),

    # Notification settings and API paths
    path('notifications/', views.notifications_page, name='notifications_page'),
    path('notifications/settings/', views.notification_settings, name='notification_settings'),
    path('notifications/settings/reset/', views.reset_notification_preferences, name='reset_notification_preferences'),
    path('notifications/api/list/', views.notification_list_api, name='notification_list_api'),
    path('notifications/api/mark-read/', views.notification_mark_read_api, name='notification_mark_read_api'),
    path('notifications/api/mark-all-read/', views.notification_mark_all_read_api, name='notification_mark_all_read_api'),
    path('notifications/api/dismiss/', views.notification_dismiss_api, name='notification_dismiss_api'),
    path('notifications/api/clear-read/', views.notification_clear_read_api, name='notification_clear_read_api'),

    # Machine status API
    path('api/machine-status/', views.machine_status_api, name='machine_status_api'),

    # Reminder check API (for GitHub Actions cron)
    path('api/check-reminders/', views.api_check_reminders, name='api_check_reminders'),

    # Temperature update API (for temperature gateway script on university network)
    path('api/update-machine-temperatures/', views.update_machine_temperatures, name='update_machine_temperatures'),

    # One-time token login (for Slack notifications)
    path('token-login/<str:token>/', views.token_login, name='token_login'),

    # Health check endpoint (for UptimeRobot and monitoring)
    path('health/', views.health_check, name='health_check'),

    # Feedback system
    path('feedback/', views.submit_feedback, name='submit_feedback'),

    # Developer pages (Tasks and Data)
    path('developer/tasks/', admin_views.developer_tasks, name='developer_tasks'),
    path('developer/tasks/update/<int:feedback_id>/', admin_views.update_feedback_status, name='update_feedback_status'),
    path('developer/tasks/delete/<int:feedback_id>/', admin_views.delete_feedback, name='delete_feedback'),
    path('developer/tasks/clear-all-completed/', admin_views.clear_all_completed_feedback, name='clear_all_completed_feedback'),
    # Removed developer_data analytics page to reduce database reads - now using Google Analytics
    # path('developer/data/', admin_views.developer_data, name='developer_data'),
    # path('developer/data/recalculate/', admin_views.recalculate_analytics, name='recalculate_analytics'),

    # Developer role promotions (superuser only)
    path('admin-users/promote-developer/<int:user_id>/', admin_views.promote_to_developer, name='promote_to_developer'),
    path('admin-users/demote-developer/<int:user_id>/', admin_views.demote_from_developer, name='demote_from_developer'),
]
