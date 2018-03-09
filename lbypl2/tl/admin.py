from django.contrib import admin
from .models import Providers, TL_info, Token, \
    User_info, Tl_model_updates, User_addresses, \
    User_emails, User_phones
# Register your models here.

admin.site.register(Providers)
admin.site.register(TL_info)
admin.site.register(Token)
admin.site.register(User_info)
admin.site.register(Tl_model_updates)
admin.site.register(User_addresses)
admin.site.register(User_emails)
admin.site.register(User_phones)