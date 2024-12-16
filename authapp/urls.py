# authapp/urls.py
from django.urls import path
from .views import login_view, logout_view
from accounts.views import dashboard  # Import from the correct location

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
]

