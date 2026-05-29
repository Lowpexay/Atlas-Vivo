from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth import logout
from django.views import View

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
	if lat is None or lon is None:
		return JsonResponse({'error': 'Latitude e longitude são obrigatórias.'}, status=400)

	location = reverse_geocode(lat, lon)
	if not location:
		return JsonResponse({'error': 'Não foi possível identificar o ponto selecionado.'}, status=404)

	weather = weather_for_location(location['lat'], location['lon'])
	country = country_profile_for_location(location)
	return JsonResponse({
		'location': location,
		'weather': weather,
		'country_profile': country,
		'clicked': {'lat': float(lat), 'lon': float(lon)},
	})


def suggest_location(request):
	q = (request.GET.get('q') or '').strip()
	if not q:
		return JsonResponse({'suggestions': []})
	suggestions = place_suggestions(q)
	return JsonResponse({'suggestions': suggestions})