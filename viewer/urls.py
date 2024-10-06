from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('viewer/<str:contig_name>/', views.viewer, name='viewer'),
    path('viewer/<str:contig_name>/heatmap-data', views.get_heatmap_data, name='get_heatmap_data'),
    path('viewer/<str:contig_name>/feature-data', views.get_feature_data, name='get_feature_data'),
    path('viewer/<str:contig_name>/search_features/', views.search_features, name='search_features'),
    path('viewer/<str:contig_name>/feature_info/', views.feature_info, name='feature_info'),
    path('crispr_plot/', views.crispr_plot, name='crispr_plot'),
    path('evaluation/', views.evaluation, name='evaluation'),
    path('about/', views.about, name='about'),
    path('cas_heatmap/', views.cas_heatmap, name='cas_heatmap'),
    path('dataprotection/', views.dataprotection, name='dataprotection'),
    path('imprint/', views.imprint, name='imprint'),

]