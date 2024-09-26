from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('viewer/<str:contig_name>/', views.viewer, name='viewer'),
    path('viewer/<str:contig_name>/heatmap-data', views.get_heatmap_data, name='get_heatmap_data'),
    path('viewer/<str:contig_name>/feature-data', views.get_feature_data, name='get_feature_data'),  # New URL Pattern
]