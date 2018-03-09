# TrueLayer models file
import requests
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.conf import settings
from django.core import serializers
import simplejson

# Create your models here.

def json_dict_generator(indict, pre=None):
    # recurses a json file to flatten it out
    pre = pre[:] if pre else []
    if isinstance(indict, dict):
        for key, value in indict.items():
            if isinstance(value, dict):
                for d in json_dict_generator(value, [key] + pre):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in json_dict_generator(v, [key] + pre):
                        yield d
            else:
                yield pre + [key, value]
    else:
        yield pre + [indict]

def json_output(json_input):
    # creates an output file from nested json and creates related, named fields for db work
    # todo check if this line is needed and if not remove - a = json_dict_generator(json_input)
    dataset = {}
    try:
        a = json_dict_generator(json_input)
        previous=None
        count=0
        while True:
            value = next(a)
            if len(value)==3:
                value[0]+="_%s" % value[1]
                value.pop(1)
            if value[0].lower()==previous:
                count+=1
                value[0]+="_%s" % count
            else:
                count=0
                previous=value[0].lower()
            dataset[value[0].lower()] = value[1]
    except StopIteration:
        pass
    finally:
        return(dataset)

class TL_info(models.Model):
    client_id = models.CharField(primary_key=True,max_length=100)
    app_name = models.CharField(max_length=50)
    client_secret = models.CharField(max_length=100)
    redirect_uri = models.URLField()
    token_url = models.URLField()
    info_url = models.URLField()
    provider_url = models.URLField()

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
        l['info_url'] = cls.objects.filter(app_name=app_name)[0].info_url
        l['provider_url'] = cls.objects.filter(app_name=app_name)[0].provider_url
        return l

class Providers(models.Model):
    provider_id = models.CharField(primary_key=True, max_length=50)
    display_name = models.CharField(max_length=150)
    logo_url = models.URLField()
    scopes = models.TextField()
    last_update = models.DateTimeField(default=timezone.now())

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
        url = TL_info.url_access()['provider_url']
        z = requests.get(url)
        # check API status code and if OK, process an update or an insert
        if z.status_code == 200:
            for obj in simplejson.loads(z.content):
                provider = cls(provider_id = obj['provider_id'],
                               display_name = obj['display_name'],
                               logo_url = obj['logo_url'],
                               scopes = obj['scopes']
                               )
                try:
                    provider.save()
                except:
                    raise Exception("There has been a unknown error in the database")
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
    token_type = models.CharField(max_length=50)

    def __str__(self):
        return ("UID : %s - Provider : %s" % (self.user,self.provider_id))

    class Meta:
        verbose_name = "User Token"
        verbose_name_plural = "User Tokens"
        unique_together = []

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
    def get_access_token(cls, username, provider_id):
        # check if the token is still valid. If so, return access token. If not, refresh then return.

        user = User.objects.get(username=username)
        # get the expiry value for the current token
        v = cls.objects.values('r_lasttime', 'expires_in', 'access_token').filter(user_id=user.id, provider_id=provider_id)[0]

        r_lasttime = v['r_lasttime']
        r_sec = v['expires_in'] - 120  # use an expiry somewhat shorter in case processing time expires a token prior to using it

        # set expiry value
        expiry = timedelta(seconds=r_sec) + r_lasttime

        if timezone.now() < expiry:  # issue the existing code
            return (v['access_token'])
        else:  # requests a new token and return it
            status=Token.update_refresh_token(username,provider_id)
            if status['code'] == 200:
                return cls.objects.filter(user_id=user.id, provider_id=provider_id)[0].access_token
            else:
                status = {'code': 400, 'desc': 'Token refresh failed.'}
                return (status)

    @classmethod
    def get_new_token(cls, username, provider_id, access_code):
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
            this_update = timezone.now()
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
            this_update = timezone.now()
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

class User_info(models.Model):
    # gathers user information from TrueLayer as provided by the bank
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider_id = models.ForeignKey(Providers, unique=False, on_delete=models.DO_NOTHING)
    full_name = models.TextField()
    date_of_birth = models.DateTimeField(default=None)
    update_timestamp = models.DateTimeField()

    class Meta:
        verbose_name = "User Information - Bank Provided"
        verbose_name_plural = "User Information - Bank Provided"
        unique_together = (('user', 'provider_id', 'full_name', 'date_of_birth'),)

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

    @classmethod
    def include_fields(cls):
        exclude_list = ['user','id','provider_id']
        field_list = [f.name for f in User_info._meta.fields if f.name not in exclude_list]
        return field_list

    @classmethod
    def get_tl_user_info_update(cls, username, provider_id):

        # identify the user and get an access token
        user = User.objects.get(username=username)
        token = Token.get_access_token(username, provider_id)

        # call truelayer for user info updates
        access_info = TL_info.url_access()
        token_phrase = "Bearer %s" % token
        headers = {'Authorization': token_phrase}
        z = requests.get(access_info['info_url'], headers=headers)
        results = z.json()['results']

        # check API status code and if OK, process an update or an insert
        if z.status_code == 200:
            print(results)
            for i in range(0,len(results)):
                print(results[i])
                update_time = results[i]['update_timestamp']
                for field in User_info.include_fields():
                    if field not in results[i].keys():
                        results[i][field]=''
                print(results[i])
                user_info = cls(user_id = user.id,
                                provider_id = Providers.objects.get(provider_id=provider_id),
                                full_name = results[i]['full_name'],
                                date_of_birth = results[i]['date_of_birth'],
                                update_timestamp = update_time
                                )
                try:
                    user_info.save()
                except:
                    raise Exception('Unknown db error')
                if 'addresses' in results[i].keys():
                    addresses=results[i]['addresses']
                    print(addresses)
                    for field in User_addresses.include_fields():
                        for j in range(0,len(addresses)):
                            if field not in addresses[j].keys():
                                addresses[j][field] = ''
                    for j in range(0,len(addresses)):
                        user_address = User_addresses(user_id = user.id,
                                                      provider_id = Providers.objects.get(provider_id = provider_id),
                                                      address = addresses[j]['address'],
                                                      city = addresses[j]['city'],
                                                      zip = addresses[j]['zip'],
                                                      country = addresses[j]['country'],
                                                      update_timestamp = update_time
                                                      )
                        try:
                            pass
                            #user_address.save()
                        except:
                            raise Exception('Unknown db error')
                if 'phones' in results[i].keys():
                    phones=results[i]['phones']
                    print(phones)
                    for j in range(0,len(phones)):
                        user_phone = User_phones(user_id = user.id,
                                                 provider_id = Providers.objects.get(provider_id = provider_id),
                                                 phones = phones[j],
                                                 update_timestamp = update_time
                                                 )
                        try:
                            pass
                            #user_phone.save()
                        except:
                            raise Exception('Unknown db error')
                if 'emails' in results[i].keys():
                    emails=results[i]['emails']
                    print(emails)
                    print()
                    for j in range(0,len(results[i]['emails'])):
                        user_email = User_emails(user_id = user.id,
                                                 provider_id = Providers.objects.get(provider_id = provider_id),
                                                 emails = emails[j],
                                                 update_timestamp = update_time
                                                 )
                        try:
                            pass
                            #user_email.save()
                        except:
                            raise Exception('Unknown db error')
            status={'code':200,'desc':'Success'}
            return(status)
        else:
            status={'code':400,'desc':'True Layer API Failure'}
            return(status)

class User_addresses(models.Model):
    # stores user address info provided by banks
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider_id = models.ForeignKey(Providers, unique=False, on_delete=models.DO_NOTHING)
    address = models.TextField(default=None)
    city = models.CharField(max_length=150, default=None)
    zip = models.CharField(max_length=50, default=None)
    country = models.CharField(max_length=150, default=None)
    update_timestamp = models.DateTimeField()

    class Meta:
        unique_together = (('user', 'provider_id'),)

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

    @classmethod
    def include_fields(cls):
        exclude_list = ['user','id','provider_id']
        field_list = [f.name for f in User_info._meta.fields if f.name not in exclude_list]
        return field_list

class User_phones(models.Model):
    # stores user phone info provided by banks
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider_id = models.ForeignKey(Providers, unique=False, on_delete=models.DO_NOTHING)
    phones = models.CharField(max_length=50)
    update_timestamp = models.DateTimeField()

    class Meta:
        unique_together = (('user', 'provider_id', 'phones'),)

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

class User_emails(models.Model):
    # stores user phone info provided by banks
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider_id = models.ForeignKey(Providers, unique=False, on_delete=models.DO_NOTHING)
    emails = models.EmailField()
    update_timestamp = models.DateTimeField()

    class Meta:
        unique_together = (('user', 'provider_id', 'emails'),)

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

class Tl_model_updates(models.Model):
    model_to_update = models.TextField() # name of the model
    fields_to_add = models.TextField() # name of the fields in json data that is not in the model
    method_to_recall = models.TextField() # name of the update routine required to be re-run once the model is up to date
    details_to_pass = models.TextField() # details such as username and provider id required to re-run the routine