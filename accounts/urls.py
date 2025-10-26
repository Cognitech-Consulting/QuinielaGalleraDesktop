# accounts/urls.py
from django.urls import path
from . import views
app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_user, name='register'),  # Use views.register_user
    path('login/', views.login_user, name='login'),           # Use views.login_user
    path('manage-users/', views.manage_users, name='manage_users'),
    path('update-tickets/<str:user_id>/', views.update_tickets, name='update_tickets'),
    path('delete-user/<str:user_id>/', views.delete_user, name='delete_user'),  # NEW: Delete user
    path('tickets/', views.get_user_tickets, name='get_user_tickets'),
    path('use-ticket/', views.use_ticket, name='use_ticket'),
    path('csrf-token/', views.csrf_token_view, name='csrf_token'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Reference views.dashboard
]