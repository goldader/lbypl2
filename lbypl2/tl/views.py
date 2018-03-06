# TrueLayer views file

from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.http import HttpResponse
from .models import Providers

# Create your views here.

class ProviderList(ListView):
    model = Providers
    template_name = "providers.html"
