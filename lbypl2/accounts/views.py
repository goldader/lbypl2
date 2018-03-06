#from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic
from django.shortcuts import HttpResponseRedirect


# Create your views here.

class SignUp(generic.CreateView):
    form_class = UserCreationForm
    #success_url = reverse_lazy('login')
    success_url = "https://auth.truelayer.com/?response_type=code&client_id=goldader-znsm&nonce=2580421759&scope=info%20accounts%20balance%20transactions%20cards%20offline_access&redirect_uri=http://localhost:3000/callback&response_mode=form_post"
    #success_url = reverse_lazy('providers')
    template_name = 'signup.html'