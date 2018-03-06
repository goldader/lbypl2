from django.contrib import admin
from .models import Providers, TL_info, Token

# Register your models here.

admin.site.register(Providers)
admin.site.register(TL_info)
admin.site.register(Token)