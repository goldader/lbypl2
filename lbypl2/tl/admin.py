from django.contrib import admin
from .models import Providers, TL_info, Token, User_info, Tl_model_updates
# Register your models here.

admin.site.register(Providers)
admin.site.register(TL_info)
admin.site.register(Token)
admin.site.register(User_info)
admin.site.register(Tl_model_updates)
