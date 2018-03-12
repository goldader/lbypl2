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
    me_url = models.URLField()

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
        l['me_url'] = cls.objects.filter(app_name=app_name)[0].me_url
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
    credentials_id = models.CharField(max_length=100, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider_id = models.ForeignKey(Providers, unique=False, on_delete=models.DO_NOTHING)
    access_token = models.TextField()
    refresh_token = models.TextField()
    r_lasttime = models.DateTimeField()
    expires_in = models.IntegerField()
    token_type = models.CharField(max_length=50)
    requested_scope = models.TextField(null=True) # based on the user's request to TL
    validated_scope = models.TextField(null=True) # validate on the token metadata return from TL

    def __str__(self):
        return ("UID : %s - Provider : %s" % (self.user,self.provider_id))

    class Meta:
        verbose_name = "User Token"
        verbose_name_plural = "User Tokens"
        unique_together = []

    @classmethod # todo add a test to simply see if it works
    def token_exists(cls, username, provider_id):
        # use to determine if a token exists at all for a given user
        user = User.objects.get(username=username)
        return cls.objects.filter(user_id=user.id, provider_id=provider_id).exists()

    @classmethod # todo add a test to simple see if it works
    def get_credential_ids(cls, username):
        # returns a list of all token credentials for a given user
        user = User.objects.get(username=username)
        return [t['credentials_id'] for t in cls.objects.values('credentials_id').filter(user_id=user.id)]

    @classmethod # todo add a test to simply see if it works
    def get_refresh_tokens(cls, username):
        # returns a list of refresh tokens for a given user
        user = User.objects.get(username=username)
        return [t['refresh_token'] for t in cls.objects.values('refresh_token').filter(user_id=user.id)]

    @classmethod
    def get_refresh_token_one(cls,credentials_id): #todo check that it returns the expected single value result
        # returns a single refresh token given a credential ID
        return cls.objects.values('refresh_token').get(credentials_id=credentials_id)['refresh_token']

    @classmethod # todo add a test to simply see if it works
    def get_access_tokens(cls, username): #todo refactor into two methods, get_single(cls, username, provider_id), get_all(cls, username)
        # check if the token is still valid. If so, return access token. If not, refresh then return.

        # get a list of all tokens and expiry values for the given user
        user = User.objects.get(username=username)
        v = cls.objects.values('credentials_id','r_lasttime', 'expires_in').filter(user_id=user.id)

        # add a for loop to evaluate the token and refresh it if old
        for i in range(0, len(v)):
            r_lasttime = v[i]['r_lasttime']
            r_sec = v[i]['expires_in'] - 120  # use an expiry somewhat shorter in case processing time expires a token prior to using it

            # set expiry value
            expiry = timedelta(seconds=r_sec) + r_lasttime

            if timezone.now() < expiry:  # leave the code in place
                pass
            else:  # requests a new token and return it
                status=Token.update_refresh_token(v[i]['credentials_id'])
                if status['code']==400:
                    return {'code': 400, 'desc': 'Token refresh failed.'}
        # [(t['access_token'],t['credentials_id']) for t in cls.objects.values('access_token').filter(user_id=user.id)]
        return (cls.objects.values('credentials_id', 'access_token').filter(user_id=user.id))

    @classmethod # todo add a test to simply see if it works
    def get_token_metadata(cls,access_token):
        # used to get metadata about the token immediately after it has been issued.
        # can used for metadata validation or update but isn't truly needed for those purposes as other models also gather the same data

        # call truelayer for token metadata
        access_info = TL_info.url_access()
        token_phrase = "Bearer %s" % access_token
        headers = {'Authorization': token_phrase}
        z = requests.get(access_info['me_url'], headers=headers)
        results = z.json()['results'][0]

        # check the api response and process or fail out
        if z.status_code == 200:  # check if API call is a success
            return({'credentials_id':results['credentials_id'],'validated_scope':results['scopes']})
        else:
            status = {'code': 400, 'desc': 'API failure. Test for TrueLayer connectivity to token meta data APIs.'}
            return(status)

    @classmethod # todo add a test to simply see if it works
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
                at_response = z.json()
                user = User.objects.get(username=username)

                # call get_token_metadata to get the token's credential and validated scope
                md_response = Token.get_token_metadata(at_response['access_token'])

                # translate the temp_dict / json into a database write procedure
                data_update=cls(
                    user_id = user.id,
                    provider_id = Providers.objects.get(provider_id=provider_id),
                    credentials_id = md_response['credentials_id'],
                    access_token = at_response['access_token'],
                    refresh_token = at_response['refresh_token'],
                    r_lasttime = this_update,
                    expires_in = at_response['expires_in'],
                    token_type = at_response['token_type'],
                    validated_scope = md_response['validated_scope']
                )
                # save the data
                data_update.save()
                status = {'code': 200, 'desc': 'Success'}
                return (status)
            else:
                status = {'code': 400, 'desc': 'API failure. Test for TrueLayer connectivity to token request APIs.'}
                return (status)

    @classmethod # todo add a test to simply see if it works
    def update_refresh_token(cls,credentials_id):
        # use to refresh the authorisation token from truelayer and update it in the database

        # get the last known refresh token for this credential
        refresh_token = Token.get_refresh_token_one(credentials_id)

        # get and configure the url info
        tl_info=TL_info.url_access()
        payload = {'grant_type': 'refresh_token', 'client_id': tl_info['client_id'], \
                   'client_secret': tl_info['client_secret'], 'refresh_token': refresh_token}
        this_update = timezone.now()
        z = requests.post(tl_info['token_url'], data=payload)  # call truelayer to get the token and set the call time

        # check the api response and process or fail out
        if z.status_code == 200:  # check if API call is a success
            temp_dict = z.json()

            # translate the temp_dict / json into a database write procedure
            data_update=cls(
                credentials_id=credentials_id,
                access_token = temp_dict['access_token'],
                refresh_token = temp_dict['refresh_token'],
                r_lasttime = this_update,
                expires_in = temp_dict['expires_in'],
                token_type = temp_dict['token_type']
            )

            # save the data
            try:
                data_update.save(update_fields=['access_token', 'refresh_token', 'r_lasttime', 'expires_in', 'token_type'])
                status = {'code': 200, 'desc': 'Success'}
                return (status)
            except:
                raise Exception('Unknown db error')
        else:
            status = {'code': 400, 'desc': 'Truelayer API failure. Potentially an invalid refresh token. TL error code = %s and message = %s' % (z.status_code, z.json()['error'])}
            return (status) #todo, if the TL error is an invalid grant register requirement to re-register the user as the token is out of synch

class User_info(models.Model):
    # gathers user information from TrueLayer as provided by the bank
    credentials_id = models.ForeignKey(Token, unique=False, on_delete=models.DO_NOTHING)
    full_name = models.TextField()
    date_of_birth = models.DateTimeField(default=None, null=True)
    update_timestamp = models.DateTimeField()

    class Meta:
        verbose_name = "User Information - Bank Provided"
        verbose_name_plural = "User Information - Bank Provided"
        unique_together = (('credentials_id','full_name'),) # todo change to token_id and full_name

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

    @classmethod
    def include_fields(cls):
        exclude_list = ['credentials_id', 'id']
        return [f.name for f in User_info._meta.fields if f.name not in exclude_list]

    @classmethod
    def get_tl_user_info_update(cls, username):

        # get the correct url string for info updates
        access_info = TL_info.url_access()

        # get all access tokens for a given user
        token_list = Token.get_access_tokens(username)

        # iterate over the tokens to get all information
        for token in token_list:
            token_phrase = "Bearer %s" % token['access_token']
            headers = {'Authorization': token_phrase}
            z = requests.get(access_info['info_url'], headers=headers)
            results = z.json()['results']

            # check API status code and if OK, iterate over the results and update records
            if z.status_code == 200:
                try:
                    #  get ids of existing records for the credentials since we cannot tell 100% if a new record is an update to an old
                    old_records = User_info.objects.filter(credentials_id=token['credentials_id'])

                    # delete old records
                    if old_records.exists():
                        old_records.delete()

                    for i in range(0,len(results)):
                        update_time = results[i]['update_timestamp']

                        # if TL does not return the field, set it to None for Django sanity, this can be replaced once we develop a serialiser
                        for field in User_info.include_fields():
                            if field not in results[i].keys():
                                results[i][field]=None

                        # write the new records
                        try:
                            # create user details first thusly setting a primary key for related tables
                            user_info = cls.objects.create(credentials_id = Token.objects.get(credentials_id=token['credentials_id']),
                                                           full_name = results[i]['full_name'],
                                                           date_of_birth = results[i]['date_of_birth'],
                                                           update_timestamp = update_time
                                                           )
                            new_record = cls.objects.get(credentials_id = token['credentials_id'], full_name = results[i]['full_name'])

                            # check if address details exist.  If so, attribute and process into the addresses model
                            # there may be more than 1 address per name so loop through addresses
                            if 'addresses' in results[i].keys():
                                addresses = results[i]['addresses']

                                for address in addresses:
                                    # attribute the address records to None where no data is sent through
                                    for field in User_addresses.include_fields():
                                        if field not in address.keys():
                                                address[field] = ''
                                    # write the results to the model
                                    try:
                                        user_address = User_addresses.objects.create(
                                            user_info_id = new_record,
                                            address=address['address'],
                                            city=address['city'],
                                            zip=address['zip'],
                                            country=address['country'],
                                            )
                                    except:
                                        raise Exception('Unknown db error')
                        except:
                            raise Exception('Unknown db error')
                except:
                    raise Exception('Unknown db error')

"""
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
                return({'code':400,'desc':'TrueLayer API Failure. TL error code = %s and message = %s' % (z.status_code, z.json()['error'])})
"""
class User_addresses(models.Model):
    # stores user address info provided by banks
    user_info_id = models.ForeignKey(User_info, unique=False, on_delete=models.CASCADE)
    address = models.TextField(default=None)
    city = models.CharField(max_length=150, default=None)
    zip = models.CharField(max_length=50, default=None)
    country = models.CharField(max_length=150, default=None)

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

    @classmethod
    def include_fields(cls):
        exclude_list = ['id', 'user_info_id']
        field_list = [f.name for f in User_addresses._meta.fields if f.name not in exclude_list]
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