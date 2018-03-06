# TrueLayer models file
import requests
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime
from django.conf import settings
from django.http import HttpRequest

# Create your models here.

class TL_info(models.Model):
    client_id = models.TextField(primary_key=True)
    app_name = models.CharField(max_length=250)
    client_secret = models.TextField()
    redirect_uri = models.TextField()
    token_url = models.TextField(default='text')

    def __str__(self):
        return self.app_name

    class Meta:
        verbose_name = "TrueLayer Keys"
        verbose_name_plural = "TrueLayer Keys"

    @classmethod
    def url_access(cls):
        app_name='goldader'
        l={}
        l['client_secret'] = cls.objects.filter(app_name=app_name)[0].client_secret
        l['client_id'] = cls.objects.filter(app_name=app_name)[0].client_id
        l['redirect_uri'] = cls.objects.filter(app_name=app_name)[0].redirect_uri
        l['token_url'] = cls.objects.filter(app_name=app_name)[0].token_url
        return l

class Providers(models.Model):
    provider_id = models.CharField(primary_key=True, max_length=250)
    display_name = models.CharField(max_length=250)
    logo_url = models.TextField()
    scopes = models.TextField()
    last_update = models.DateTimeField(default=datetime.utcnow())

    class Meta:
        verbose_name = "TrueLayer Provider"
        verbose_name_plural = "TrueLayer Providers"

    def __str__(self):
        return self.display_name

    @classmethod
    def provider_nm(cls,provider_id):
        return cls.objects.filter(provider_id=provider_id)[0].display_name

    @classmethod
    def provider_scope(cls,provider_id):
        return cls.objects.filter(provider_id=provider_id)[0].scopes

    @classmethod
    def provider_exists(cls,provider_id):
        return cls.objects.filter(provider_id=provider_id).exists()

    @classmethod
    def provider_details(cls,provider_id):
        return (cls.objects.filter(provider_id=provider_id).values())[0]

    @classmethod
    def providers_all(cls):
        return list(cls.objects.values())

    @classmethod
    def update_providers(cls):
        # Use to populate and update the providers table.
        url = "https://auth.truelayer.com/api/providers"
        z = requests.get(url)
        # check API status code and if OK, process an update or an insert
        if z.status_code==200:
            my_dict = {}
            providers = (z.json()) # todo add a check for the provider here.  if provider_id not in table run providers update first
            for i in range(0,len(providers)):
                my_dict = providers[i]
                provider = cls(
                    provider_id=my_dict["provider_id"].lower(),
                    display_name=my_dict["display_name"],
                    logo_url=my_dict["logo_url"],
                    scopes=my_dict["scopes"],
                    last_update=timezone.now(),
                )
                provider.save()
            status={'code':200,'desc':'Success'}
            return(status)
        else:
            status={'code':400,'desc':'True Layer API Failure'}
            return(status)

class Token(models.Model):
    # establishes a token for a user at a given provider
    # todo refactor 1:1 user to provider relationship. Need to update so users can have multiple tokens for the same provider
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider_id = models.ForeignKey(Providers, unique=False, on_delete=models.DO_NOTHING)
    access_token = models.TextField()
    refresh_token = models.TextField()
    r_lasttime = models.DateTimeField()
    expires_in = models.IntegerField()
    token_type = models.TextField()

    def __str__(self):
        return self.refresh_token

    @classmethod
    def token_exists(cls, username, provider_id):
        user = User.objects.get(username=username)
        return cls.objects.filter(user_id=user.id,provider_id=provider_id).exists()

    @classmethod
    def get_refresh_token(cls, username, provider_id):
        # refresh token for the given user and provider combination
        user = User.objects.get(username=username)
        return cls.objects.filter(user_id=user.id,provider_id=provider_id)[0].refresh_token

    @classmethod
    def new_token(cls, username, provider_id, access_code):
        # use to acquire a new access token from truelayer and update it in the database
        # requires the front end to have already been provided an authorisation token called access_code

        # determine if the user / provider combination already exist
        if Token.token_exists(username, provider_id) == True:
            status = {'code': 400, 'desc': 'User/provider combination already exist.'}
            return (status)

        # the user / provider combination does not exist so call Truelayer and exchange code for access token
        else:
            tl_info=TL_info.url_access()
            payload = {'grant_type': 'authorization_code', 'client_id': tl_info['client_id'], \
                       'client_secret': tl_info['client_secret'], 'redirect_uri': tl_info['redirect_uri'], 'code': access_code}
            this_update = datetime.utcnow()
            z = requests.post(tl_info['token_url'], data=payload)  # call truelayer to get the token and set the call time

            # check the api response and process or fail out
            if z.status_code == 200:  # check if API call is a success
                temp_dict = z.json()
                user = User.objects.get(username=username)

                # translate the temp_dict / json into a database write procedure
                data_update=cls(
                    user_id = user.id,
                    provider_id = Providers.objects.get(provider_id=provider_id),
                    access_token = temp_dict['access_token'],
                    refresh_token = temp_dict['refresh_token'],
                    r_lasttime = this_update,
                    expires_in = temp_dict['expires_in'],
                    token_type = temp_dict['token_type']
                )
                # save the data
                data_update.save()
                status = {'code': 200, 'desc': 'Success'}
                return (status)
            else:
                status = {'code': 400, 'desc': 'API failure. Test for TrueLayer connectivity to token request APIs.'}
                return (status)

    @classmethod
    def update_refresh_token(cls,username, provider_id):
        # use to refresh the authorisation token from truelayer and update it in the database

        # determine if the user / provider combination already exist
        if Token.token_exists(username, provider_id) == False:
            status = {'code': 400, 'desc': 'User/provider combination does not exist.'}
            return (status)

        else:
             # get the last known refresh token for the user / provider combination
            refresh_token = Token.get_refresh_token(username, provider_id)

            # get and configure the url info
            tl_info=TL_info.url_access()
            payload = {'grant_type': 'refresh_token', 'client_id': tl_info['client_id'], \
                       'client_secret': tl_info['client_secret'], 'refresh_token': refresh_token}
            this_update = datetime.utcnow()
            z = requests.post(tl_info['token_url'], data=payload)  # call truelayer to get the token and set the call time

            # check the api response and process or fail out
            if z.status_code == 200:  # check if API call is a success
                temp_dict = z.json()
                user = User.objects.get(username=username)

                # translate the temp_dict / json into a database write procedure
                data_update=cls(
                    id = Token.objects.get(user_id=user.id, provider_id=provider_id).id,
                    user_id = user.id,
                    provider_id = Providers.objects.get(provider_id=provider_id),
                    access_token = temp_dict['access_token'],
                    refresh_token = temp_dict['refresh_token'],
                    r_lasttime = this_update,
                    expires_in = temp_dict['expires_in'],
                    token_type = temp_dict['token_type']
                )
                # save the data
                data_update.save()
                status = {'code': 200, 'desc': 'Success'}
                return (status)
            else:
                status = {'code': 400, 'desc': 'API failure. Test for TrueLayer connectivity to token request APIs.'}
                return (status)
