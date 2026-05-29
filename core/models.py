from django.db import models
from django.conf import settings


class Favorite(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
	name = models.CharField(max_length=255)
	lat = models.FloatField()
	lon = models.FloatField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.name} ({self.lat:.5f}, {self.lon:.5f})"

# Create your models here.
