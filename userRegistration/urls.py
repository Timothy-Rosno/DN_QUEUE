from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),

    # Password reset flow
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('security-question/', views.security_question, name='security_question'),
    path('reset-password/', views.reset_password, name='reset_password'),

    # Username recovery
    path('recover-username/', views.recover_username, name='recover_username'),

    # Security question management
    path('change-security-question/', views.change_security_question, name='change_security_question'),
]
