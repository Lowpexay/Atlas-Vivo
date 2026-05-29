from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth import logout
from django.views import View
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest
import json

from .models import Favorite

from .services import geocode_place, reverse_geocode, weather_for_location, country_profile_for_location, place_suggestions


class AppLoginView(LoginView):
	template_name = 'registration/login.html'


class RegisterView(View):
	template_name = 'registration/signup.html'

	def get(self, request):
		form = UserCreationForm()
		return render(request, self.template_name, {'form': form})

	def post(self, request):
		form = UserCreationForm(request.POST)
		if form.is_valid():
			form.save()
			return redirect('login')
		return render(request, self.template_name, {'form': form})


class DashboardView(LoginRequiredMixin, View):
	template_name = 'core/dashboard.html'

	def get(self, request):
		return render(request, self.template_name, {
			'initial_place': 'Brasil',
		})


@login_required
@require_POST
def logout_view(request):
	logout(request)
	return redirect('login')


def search_location(request):
	query = (request.GET.get('q') or '').strip()
	if not query:
		return JsonResponse({'error': 'Informe um nome para pesquisar.'}, status=400)

	location = geocode_place(query)
	if not location:
		return JsonResponse({'error': 'Local não encontrado.'}, status=404)

	weather = weather_for_location(location['lat'], location['lon'])
	country = country_profile_for_location(location)
	return JsonResponse({
		'location': location,
		'weather': weather,
		'country_profile': country,
	})


def lookup_point(request):
	lat = request.GET.get('lat')
	lon = request.GET.get('lon')
	label = (request.GET.get('label') or '').strip()
	if lat is None or lon is None:
		return JsonResponse({'error': 'Latitude e longitude são obrigatórias.'}, status=400)

	# tolerate comma decimal separators from localized URLs
	if isinstance(lat, str):
		lat = lat.replace(',', '.')
	if isinstance(lon, str):
		lon = lon.replace(',', '.')
	try:
		lat_f = float(lat)
		lon_f = float(lon)
	except Exception:
		return JsonResponse({'error': 'Latitude e longitude inválidas.'}, status=400)

	location = reverse_geocode(lat_f, lon_f)
	if not location:
		location = {
			'lat': lat_f,
			'lon': lon_f,
			'display_name': 'Ponto favoritado',
			'query': 'Ponto favoritado',
		}
	if label:
		location['display_name'] = label
		location['query'] = label

	weather = weather_for_location(location['lat'], location['lon'])
	country = country_profile_for_location(location) if location else None
	return JsonResponse({
		'location': location,
		'weather': weather,
		'country_profile': country,
		'clicked': {'lat': lat_f, 'lon': lon_f},
	})


def suggest_location(request):
	q = (request.GET.get('q') or '').strip()
	if not q:
		return JsonResponse({'suggestions': []})
	suggestions = place_suggestions(q)
	return JsonResponse({'suggestions': suggestions})


@login_required
@require_POST
def add_favorite(request):
	try:
		payload = json.loads(request.body.decode('utf-8'))
	except Exception:
		return HttpResponseBadRequest('Invalid payload')

	name = (payload.get('name') or '').strip()
	lat = payload.get('lat')
	lon = payload.get('lon')
	if not name or lat is None or lon is None:
		return JsonResponse({'error': 'name, lat and lon are required'}, status=400)

	lat_f = float(lat)
	lon_f = float(lon)
	# avoid duplicate favorites within a small radius
	eps = 0.0005
	existing = Favorite.objects.filter(
		user=request.user,
		lat__gte=lat_f - eps, lat__lte=lat_f + eps,
		lon__gte=lon_f - eps, lon__lte=lon_f + eps,
	).first()
	if existing:
		return JsonResponse({'ok': True, 'id': existing.id, 'existing': True})

	fav = Favorite.objects.create(user=request.user, name=name, lat=lat_f, lon=lon_f)
	return JsonResponse({'ok': True, 'id': fav.id, 'existing': False})


@login_required
def favorites_page(request):
	qs = Favorite.objects.filter(user=request.user).order_by('-created_at')
	# enrich favorites with reverse-geocode data (city, region, country)
	enriched = []
	for f in qs:
		loc = reverse_geocode(f.lat, f.lon) or {}
		address = (loc.get('raw') or {}).get('address', {}) or {}
		city = address.get('city') or address.get('town') or address.get('village') or address.get('county') or ''
		region = address.get('state') or address.get('region') or ''
		country = address.get('country') or loc.get('country') or ''
		enriched.append({
			'id': f.id,
			'name': f.name,
			'lat': f.lat,
			'lon': f.lon,
			'city': city,
			'region': region,
			'country': country,
			'created_at': f.created_at,
		})
	return render(request, 'core/favorites.html', {'favorites': enriched})


@login_required
@require_POST
def remove_favorite(request, favorite_id: int):
	fav = get_object_or_404(Favorite, id=favorite_id, user=request.user)
	fav.delete()
	return redirect('favorites_page')


def check_favorite(request):
	"""Return whether the current user already favorited a nearby point.
	Query params: lat, lon
	"""
	lat = request.GET.get('lat')
	lon = request.GET.get('lon')
	try:
		lat = float(lat)
		lon = float(lon)
	except Exception:
		return JsonResponse({'favorited': False})

	# small epsilon ~50m
	eps = 0.0005
	if not request.user.is_authenticated:
		return JsonResponse({'favorited': False})

	fav = Favorite.objects.filter(
		user=request.user,
		lat__gte=lat - eps, lat__lte=lat + eps,
		lon__gte=lon - eps, lon__lte=lon + eps,
	).first()
	if not fav:
		return JsonResponse({'favorited': False})
	return JsonResponse({'favorited': True, 'id': fav.id})