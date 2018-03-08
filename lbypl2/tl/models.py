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
    token_type = models.TextField()

    def __str__(self):
        return ("UID : %s - Provider : %s" % (self.user,self.provider_id))

    class Meta:
        verbose_name = "User Token"
        verbose_name_plural = "User Tokens"

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
    update_timestamp = models.DateTimeField()
    full_name = models.TextField()
    addresses_address = models.TextField()
    addresses_city = models.TextField()
    addresses_zip = models.CharField(max_length=50)
    addresses_country = models.CharField(max_length=150)
    emails = models.EmailField()
    emails_1 = models.EmailField()
    emails_2 = models.EmailField()
    phones = models.CharField(max_length=50)
    phones_1 = models.CharField(max_length=50)
    phones_2 = models.CharField(max_length=50)
    account_id = models.TextField()
    account_type = models.TextField()
    display_name = models.TextField()
    currency = models.CharField(max_length=50)
    account_number_iban = models.CharField(max_length=50)
    account_number_swift_bic = models.CharField(max_length=15)
    account_number_number = models.CharField(max_length=50)
    account_number_sort_code = models.CharField(max_length=15)
    provider_display_name = models.TextField()
    provider_provider_id = models.CharField(max_length=250)
    provider_logo_uri = models.TextField()

    class Meta:
        verbose_name = "User Information - Bank Provided"
        verbose_name_plural = "User Information - Bank Provided"

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

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

        # send results to json parsing routines
        results = json_output(results[0])

        # check if the json fields map to the db and generate a data update and missing fields list
        field_list = [f.name for f in User_info._meta.fields]
        missing_fields=[]
        data_to_update = "user_id = user.id, provider_id = Providers.objects.get(provider_id=provider_id),"
        count=1
        for k,v in results.items():
            if k in field_list:
                if count<len(results.keys()):
                    data_to_update+="%s = '%s'," % (k,v)
                else:
                    data_to_update+="%s = '%s'" % (k,v)
                count+=1
            else:
                count+=1
                missing_fields.append(k)

        # check if there are any missing fields.  If so, write to the error model
        if len(missing_fields)>0:
            model_to_update = str(cls._meta.label)
            data_update=Tl_model_updates(
                model_to_update= model_to_update,
                fields_to_add = missing_fields,
                method_to_recall = 'get_tl_user_info_update',  # Todo refactor to get the method name dynamically
                details_to_pass = [username,provider_id]
            )
            data_update.save()
            status = {'code': 201, 'desc': 'Partial update. Check Tl_model_updates for required updates.'} # Todo figure out how to use Raise for errors
            #return(status)

        # write the real results to the model
        print(data_to_update)

        #data_update=cls(data_to_update)
        #data_update = cls(data_update)
        #data_update.save

        #if status == None:
        #    status = {'code': 200, 'desc': 'Success'}
        #    return (status)
        #else:
        #    return(status)
        # quit the routine, write the data to the missing data model

class Tl_model_updates(models.Model):
    model_to_update = models.TextField() # name of the model
    fields_to_add = models.TextField() # name of the fields in json data that is not in the model
    method_to_recall = models.TextField() # name of the update routine required to be re-run once the model is up to date
    details_to_pass = models.TextField() # details such as username and provider id required to re-run the routine