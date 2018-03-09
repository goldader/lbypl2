from django.contrib import admin
from .models import Providers, TL_info, Token, \
    User_info, Tl_model_updates, User_addresses, \
    User_emails, User_phones

class EmailInLine(admin.TabularInline):
    model = User_emails
    extra = 0

class Tl_user_admin(admin.ModelAdmin):
    fieldsets = [
        ('User Details', {'fields': ['user', 'full_name', 'date_of_birth']}),
        ('Bank', {'fields': ['provider_id']}),
        ('Update', {'fields': ['update_timestamp']})
    ]
#    inlines = [EmailInLine]

# Register your models here.
admin.site.register(Providers)
admin.site.register(TL_info)
admin.site.register(Token)
admin.site.register(User_info, Tl_user_admin)
admin.site.register(Tl_model_updates)
admin.site.register(User_addresses)
admin.site.register(User_emails)
admin.site.register(User_phones)

