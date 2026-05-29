from django.urls import path

from .views import AppLoginView, DashboardView, RegisterView, logout_view, lookup_point, search_location

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('login/', AppLoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', logout_view, name='logout'),
    path('api/search/', search_location, name='search_location'),
    path('api/lookup/', lookup_point, name='lookup_point'),
]