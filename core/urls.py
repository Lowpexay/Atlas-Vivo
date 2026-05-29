from django.urls import path

from .views import AppLoginView, DashboardView, RegisterView, logout_view, lookup_point, search_location, suggest_location, add_favorite, favorites_page, check_favorite, remove_favorite

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('login/', AppLoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', logout_view, name='logout'),
    path('api/search/', search_location, name='search_location'),
    path('api/lookup/', lookup_point, name='lookup_point'),
    path('api/suggest/', suggest_location, name='suggest_location'),
    path('api/favorite/', add_favorite, name='add_favorite'),
    path('api/favorite/check/', check_favorite, name='check_favorite'),
    path('favorites/', favorites_page, name='favorites_page'),
    path('favorites/<int:favorite_id>/delete/', remove_favorite, name='remove_favorite'),
]