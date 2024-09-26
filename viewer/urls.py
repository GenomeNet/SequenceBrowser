from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('viewer/<str:contig_name>/', views.viewer, name='viewer'),
]