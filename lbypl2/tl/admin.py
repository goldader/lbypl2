from django.contrib import admin
from .models import Providers, TL_info, Token, \
    User_info, Tl_model_updates, User_addresses, \
    User_emails, User_phones, Account, \
    Account_balance

class EmailInLine(admin.TabularInline):
    model = User_emails
    extra = 0

class PhoneInLine(admin.TabularInline):
    model = User_phones
    extra = 0

class AddressInLine(admin.StackedInline):
    model = User_addresses
    extra = 0

class TokenInLine(admin.StackedInline):
    model = Token
    extra = 0

class Tl_user_admin(admin.ModelAdmin):
    fieldsets = [
        ('Credential ID', {'fields': ['credentials_id']}),
        ('User Details', {'fields': ['full_name', 'date_of_birth']}),
        ('Last Update', {'fields': ['update_timestamp']})
    ]
    inlines = [EmailInLine, AddressInLine, PhoneInLine]


# Register your models here.
admin.site.register(Providers)
admin.site.register(TL_info)
admin.site.register(Token)
admin.site.register(User_info, Tl_user_admin)
admin.site.register(Tl_model_updates)
admin.site.register(Account)
admin.site.register(Account_balance)