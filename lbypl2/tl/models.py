# TrueLayer models file
import requests
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.conf import settings
from django.core import serializers
import simplejson
from django.core.exceptions import ObjectDoesNotExist

# Create your models here.
# Todo update all classes to check permissions before progressing. Add this logic into the methods to onboard users or update records

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
    account_url = models.URLField()
    card_url = models.URLField()

    def __str__(self):
        return self.app_name

    class Meta:
        verbose_name = "TrueLayer Keys"
        verbose_name_plural = "TrueLayer Keys"

    @classmethod
    def url_access(cls): #todo consider refactoring this to a queryset object and updating URL calls in models
        app_name='goldader'
        l={}
        l['client_secret'] = cls.objects.filter(app_name=app_name)[0].client_secret
        l['client_id'] = cls.objects.filter(app_name=app_name)[0].client_id
        l['redirect_uri'] = cls.objects.filter(app_name=app_name)[0].redirect_uri
        l['token_url'] = cls.objects.filter(app_name=app_name)[0].token_url
        l['info_url'] = cls.objects.filter(app_name=app_name)[0].info_url
        l['provider_url'] = cls.objects.filter(app_name=app_name)[0].provider_url
        l['me_url'] = cls.objects.filter(app_name=app_name)[0].me_url
        l['account_url'] = cls.objects.filter(app_name=app_name)[0].account_url
        l['card_url'] = cls.objects.filter(app_name=app_name)[0].card_url
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
    credentials_id = models.CharField(max_length=128, primary_key=True)
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
        # Todo add a safe trap for DoesNotExist. Add this trap to other, similar methods
        return cls.objects.values('refresh_token').get(credentials_id=credentials_id)['refresh_token']

    @classmethod # todo add a test to simply see if it works
    def get_access_tokens(cls, username):
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
                status = Token.update_refresh_token(v[i]['credentials_id'])
                if status['code']==400:
                    return {'code': 400, 'desc': 'Token refresh failed.'}
        return (cls.objects.values('credentials_id', 'access_token').filter(user_id=user.id))

    @classmethod
    def get_access_token_one(cls,credentials_id):
        # returns a single access token given a credential ID

        v = cls.objects.values('r_lasttime', 'expires_in').filter(credentials_id = credentials_id)
        r_lasttime = v[0]['r_lasttime']
        r_sec = v[0]['expires_in'] - 120 # user an expiry somewhat shorter in case processing time expires a token in flight

        # set expiry value
        expiry = timedelta(seconds=r_sec) + r_lasttime

        if timezone.now() < expiry:
            pass
        else:
            status = Token.update_refresh_token(credentials_id)
            if status['code'] == 400:
                return {'code': 400, 'desc': 'Token refresh failed.'}
        return cls.objects.values('access_token').get(credentials_id = credentials_id)['access_token']

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
    full_name = models.CharField(max_length=150)
    date_of_birth = models.DateTimeField(default=None, null=True)
    update_timestamp = models.DateTimeField()

    def __str__(self):
        return (self.full_name)

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
                                        raise Exception('Unknown db error during address creation')

                            # check if there are phone details and if so, write them to the phone model
                            if 'phones' in results[i].keys():
                                phones = results[i]['phones']
                                for phone in phones:
                                    try:
                                        user_phone = User_phones.objects.create(
                                            user_info_id = new_record,
                                            phones=phone.strip()
                                        )
                                    except:
                                        raise Exception('Unknown db error during phone creation')

                            # check if there are emails and if so, write them to the email model
                            if 'emails' in results[i].keys():
                                emails = results[i]['emails']
                                for email in emails:
                                    try:
                                        user_email = User_emails.objects.create(
                                            user_info_id = new_record,
                                            emails=email.strip()
                                        )
                                    except:
                                        raise Exception('Unknown db error during email creation')
                        except:
                            raise Exception('Unknown db error during user info record creation.')
                except:
                    raise Exception('Unknown db error during delete of old records')
            else:
                return ({'code': 400,
                          'desc': 'Truelayer User Info API failure. TL error code = %s and message = %s' % (
                          z.status_code, z.json()['error'])
                          })
        return({'code': 200,'desc': 'Success'})

class User_addresses(models.Model):
    # stores user address info provided by banks
    user_info_id = models.ForeignKey(User_info, unique=False, on_delete=models.CASCADE)
    address = models.TextField()
    city = models.CharField(max_length=150)
    zip = models.CharField(max_length=25)
    country = models.CharField(max_length=150)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

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
    user_info_id = models.ForeignKey(User_info, unique=False, on_delete=models.CASCADE)
    phones = models.CharField(max_length=32)

    def __str__(self):
        return (self.phones)

    class Meta:
        verbose_name = "Phone"
        verbose_name_plural = "Phones"

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

class User_emails(models.Model):
    # stores user emails provided by banks
    user_info_id = models.ForeignKey(User_info, unique=False, on_delete=models.CASCADE)
    emails = models.EmailField()

    def __str__(self):
        return(self.emails)

    class Meta:
        verbose_name = "Email"
        verbose_name_plural = "Emails"

    @property
    def fields(self):
        return [f.name for f in self._meta.fields]

class Tl_model_updates(models.Model):
    model_to_update = models.TextField() # name of the model
    fields_to_add = models.TextField() # name of the fields in json data that is not in the model
    method_to_recall = models.TextField() # name of the update routine required to be re-run once the model is up to date
    details_to_pass = models.TextField() # details such as username and provider id required to re-run the routine
    #todo evaulate the need for this model and delete if unnecessary

class Account(models.Model):
    # list account details for a given token.  multiple accounts may exist per token
    credentials_id = models.ForeignKey(Token, on_delete=models.DO_NOTHING)
    account_id = models.CharField(max_length=100, primary_key=True)
    account_type = models.CharField(max_length=50)
    account_number_iban = models.CharField(max_length=34, null=True)
    account_number_number = models.CharField(max_length=30, null=True)
    account_number_sort_code = models.CharField(max_length=20, null=True)
    account_number_swift_bic = models.CharField(max_length=11, null=True)
    currency = models.CharField(max_length=3)
    display_name = models.CharField(max_length=150, null=True)
    update_timestamp = models.DateTimeField()
    provider_id = models.ForeignKey(Providers, on_delete=models.DO_NOTHING)

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    def __str__(self):
        return ("%s : %s (%s)" % (self.provider_id, self.display_name, self.account_number_number))

    @classmethod
    def include_fields(cls):
        exclude_list = ['credentials_id', 'id', 'account_id', 'provider_id']
        return [f.name for f in Account._meta.fields if f.name not in exclude_list]

    @classmethod
    def get_accounts(cls,username):
        return Account.objects.values("credentials_id", "account_id").filter(credentials_id__in=Token.get_credential_ids(username))

    @classmethod
    def get_accounts_update(cls, username):

        # get the correct url string for info updates
        access_info = TL_info.url_access()

        # get all access tokens for a given user
        token_list = Token.get_access_tokens(username)

        # iterate over the tokens to get all information
        for token in token_list:
            token_phrase = "Bearer %s" % token['access_token']
            headers = {'Authorization': token_phrase}
            z = requests.get(access_info['account_url'], headers=headers)
            results = z.json()['results']

            # check API status code and if OK, iterate over the results and update records
            if z.status_code == 200: #Todo add a test and a trap for a provider_id that does not exist in the Providers table. If this happens, run provider update
                try:
                    for i in range(0,len(results)):
                        # flatten the embedded records
                        new_results = json_output(results[i])

                        # if TL does not return the field, set it to None for Django sanity, this can be replaced once we develop a serialiser
                        for field in Account.include_fields():
                            if field not in new_results.keys():
                                new_results[field]=None

                        # write the new records
                        account_info = cls(
                            credentials_id = Token.objects.get(credentials_id=token['credentials_id']),
                            account_id = new_results['account_id'],
                            account_type = new_results['account_type'],
                            account_number_iban = new_results['account_number_iban'],
                            account_number_number = new_results['account_number_number'],
                            account_number_sort_code = new_results['account_number_sort_code'],
                            account_number_swift_bic = new_results['account_number_swift_bic'],
                            currency = new_results['currency'],
                            display_name = new_results['display_name'],
                            update_timestamp = new_results['update_timestamp'],
                            provider_id = Providers.objects.get(provider_id = new_results['provider_provider_id'])
                        )
                        account_info.save()
                except:
                    raise Exception('Unknown db error')
            else:
                return ({'code': 400,
                          'desc': 'Truelayer User Account API failure. TL error code = %s and message = %s' % (
                          z.status_code, z.json()['error'])
                         })
        return({'code': 200,'desc':'Success'})

class Account_balance(models.Model):
    account_id = models.ForeignKey(Account, on_delete=models.CASCADE)
    available = models.DecimalField(max_digits=13,decimal_places=2)
    currency = models.CharField(max_length=3)
    current = models.DecimalField(max_digits=13,decimal_places=2)
    update_timestamp = models.DateTimeField()

    class Meta:
        verbose_name = "Latest Balance"
        verbose_name_plural = "Latest Balance"

    @classmethod
    def include_fields(cls):
        exclude_list = ['id', 'account_id']
        return [f.name for f in Account_balance._meta.fields if f.name not in exclude_list]

    @classmethod
    def latest_available_balance(cls,account_id):
        try:
            balance = Account_balance.objects.values("available").filter(account_id = account_id).latest('update_timestamp')
        except ObjectDoesNotExist:
            return ({'code': 201,'desc': 'Card account does not exist'})
        return balance

    @classmethod
    def latest_current_balance(cls,account_id):
        try:
            balance = Account_balance.objects.values("current").filter(account_id = account_id).latest('update_timestamp')
        except ObjectDoesNotExist:
            return ({'code': 201,'desc': 'Card account does not exist'})
        return balance

    @classmethod
    def get_account_balances_update(cls, username):

        # get the correct url string for updates
        access_info = TL_info.url_access()

        # get all accounts and credentials for a given user
        account_list = Account.get_accounts(username)

        # iterate over the tokens to get all information
        for i in range(0,len(account_list)):
            access_token = Token.get_access_token_one(account_list[i]['credentials_id'])
            token_phrase = "Bearer %s" % access_token
            headers = {'Authorization': token_phrase}
            url = "%s/%s/balance" % (access_info['account_url'],account_list[i]['account_id'])
            z = requests.get(url, headers=headers)

            # check API status code and if OK, iterate over the results and update records
            if z.status_code == 200:
                results = z.json()['results']
                try:
                    # if TL does not return the field, set it to None for Django sanity, this can be replaced once we develop a serialiser
                    for field in Account_balance.include_fields():
                        if field not in results[0].keys():
                            results[0][field]=None
                    # write the new records
                    account_balance = cls(
                        account_id = Account.objects.get(account_id = account_list[i]['account_id']),
                        available = results[0]['available'],
                        currency = results[0]['currency'],
                        current = results[0]['current'],
                        update_timestamp = results[0]['update_timestamp']
                        )
                    account_balance.save()
                except:
                    raise Exception('Unknown db error')
            else:
                return ({'code': 400,
                          'desc': 'Truelayer Account Balance API failure. TL error code = %s and message = %s' % (
                          z.status_code, z.json()['error'])
                         })
        return({'code': 200,'desc':'Success'})

class Account_trans(models.Model):
    account_id = models.ForeignKey(Account, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=128,primary_key=True)
    timestamp = models.DateTimeField()
    description = models.TextField(null=True)
    transaction_type = models.CharField(max_length=50)
    transaction_category = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=13,decimal_places=2)
    currency = models.CharField(max_length=3)
    meta = models.TextField(null=True)

    class Meta:
        verbose_name = "Account Transactions"
        verbose_name_plural = "Account Transactions"
        get_latest_by = "timestamp"

    @classmethod
    def include_fields(cls):
        exclude_list = ['account_id','transaction_id']
        return [f.name for f in Account_trans._meta.fields if f.name not in exclude_list]

    @classmethod
    def get_account_trans(cls,username):

        # get the correct url string for info updates
        access_info = TL_info.url_access()

        # get all accounts and credentials for a given user
        account_list = Account.get_accounts(username)

        # iterate over the tokens to get all information
        for i in range(0, len(account_list)):
            # establish the correct url string for each account
            access_token = Token.get_access_token_one(account_list[i]['credentials_id'])
            token_phrase = "Bearer %s" % access_token
            headers = {'Authorization': token_phrase}

            try: # trap for null recordsets
                latest = Account_trans.objects.values_list('timestamp').filter(account_id = account_list[i]['account_id']).latest('timestamp')
                f_date = latest[0].strftime("%Y-%m-%d")
            except ObjectDoesNotExist:
                f_date = (timezone.now() - timedelta(days=365)).strftime("%Y-%m-%d")

            t_date = timezone.now().strftime("%Y-%m-%d")

            url = "%s/%s/transactions?from=%s&to=%s" % (access_info['account_url'], account_list[i]['account_id'],f_date,t_date)
            z = requests.get(url, headers=headers)

            if z.status_code == 200:
                results = z.json()['results']

                # check for fields that are not provided so Django is happy (prefer NoSQL approach)
                include_fields = Account_trans.include_fields()

                # set the accoutn in advance so it is not called during looping
                account=Account.objects.get(account_id = account_list[i]['account_id']) #todo check other places to pull ID setting out of the loop and update where appropriate

                for i in range(0,len(results)):
                    new_results = results[i]

                    # check the include fields (keeping Django happy again)
                    for field in include_fields: # Todo refactor to a comprehension for speed
                        if field not in new_results.keys():
                            new_results[field] = None

                    # write the data out (no bulk adds in Django ... thank you django, let's add 1 by 1)
                    try:
                        account_trans = cls(
                            account_id=account,
                            transaction_id = new_results['transaction_id'],
                            timestamp = new_results['timestamp'],
                            description = new_results['description'],
                            transaction_type = new_results['transaction_type'],
                            transaction_category = new_results['transaction_category'],
                            amount = new_results['amount'],
                            currency = new_results['currency'],
                            meta = new_results['meta'],
                           )
                        account_trans.save()
                    except:
                        raise Exception('Unknown db error')
            else:
                return ({'code': 400,
                         'desc': 'Truelayer Account Transaction API failure. TL error code = %s and message = %s' % (
                             z.status_code, z.json()['error'])
                         })
        return ({'code': 200, 'desc': 'Success'})

class Cards(models.Model):
    # list account details for a given token.  multiple accounts may exist per token
    credentials_id = models.ForeignKey(Token, on_delete=models.DO_NOTHING)
    card_account_id = models.CharField(max_length=100, primary_key=True)
    card_network = models.CharField(max_length=50)
    card_type = models.CharField(max_length=50)
    currency = models.CharField(max_length=3)
    display_name = models.CharField(max_length=150, null=True)
    partial_card_number = models.CharField(max_length=4)
    name_on_card = models.CharField(max_length=150,null=True)
    valid_from = models.DateTimeField(null=True)
    valid_to = models.DateTimeField(null=True)
    update_timestamp = models.DateTimeField()
    provider_meta = models.TextField(null=True)

    def __str__(self):
        return ("%s : %s (%s)" % (self.card_network, self.card_type, self.partial_card_number))

    class Meta:
        verbose_name = "Card Account"
        verbose_name_plural = "Card Accounts"

    @classmethod
    def include_fields(cls):
        exclude_list = ['credentials_id', 'id', 'card_account_id', 'provider_meta']
        return [f.name for f in Cards._meta.fields if f.name not in exclude_list]

    @classmethod
    def get_card_accounts(cls,username):
        return Cards.objects.values("credentials_id", "card_account_id").filter(credentials_id__in=Token.get_credential_ids(username))

    @classmethod
    def get_card_accounts_update(cls, username):

        # get the correct url string for info updates
        access_info = TL_info.url_access()

        # get all access tokens for a given user
        token_list = Token.get_access_tokens(username)

        # iterate over the tokens to get all information
        for token in token_list:
            token_phrase = "Bearer %s" % token['access_token']
            headers = {'Authorization': token_phrase}
            z = requests.get(access_info['card_url'], headers=headers)
            results = z.json()['results']

            # check API status code and if OK, iterate over the results and update records
            if z.status_code == 200: #Todo add a test and a trap for a provider_id that does not exist in the Providers table. If this happens, run provider update
                try:
                    for i in range(0,len(results)):
                        # flatten the embedded records
                        new_results = results[i]

                        # if TL does not return the field, set it to None for Django sanity, this can be replaced once we develop a serialiser
                        for field in Cards.include_fields():
                            if field not in new_results.keys():
                                new_results[field]=None

                        # write the new records
                        card_info = cls(
                            credentials_id = Token.objects.get(credentials_id=token['credentials_id']),
                            card_account_id = new_results['account_id'],
                            card_network = new_results['card_network'],
                            card_type = new_results['card_type'],
                            currency = new_results['currency'],
                            display_name = new_results['display_name'],
                            partial_card_number = new_results['partial_card_number'],
                            name_on_card = new_results['name_on_card'],
                            valid_from = new_results['valid_from'],
                            valid_to = new_results['valid_to'],
                            update_timestamp = new_results['update_timestamp'],
                            provider_meta = new_results['provider']
                        )
                        card_info.save()

                except:
                    raise Exception('Unknown db error')
            else:
                return ({'code': 400,
                          'desc': 'Truelayer Card Account API failure. TL error code = %s and message = %s' % (
                          z.status_code, z.json()['error'])
                         })
        return({'code': 200,'desc':'Success'})

class Card_account_balance(models.Model):
    card_account_id = models.ForeignKey(Cards, on_delete=models.CASCADE)
    available = models.DecimalField(max_digits=13, decimal_places=2, null=True)
    currency = models.CharField(max_length=3)
    current = models.DecimalField(max_digits=13, decimal_places=2, null=True)
    credit_limit = models.DecimalField(max_digits=13, decimal_places=2, null=True)
    last_statement_balance = models.DecimalField(max_digits=13, decimal_places=2, null=True)
    last_statement_date = models.DateTimeField(null=True)
    payment_due = models.DecimalField(max_digits=13, decimal_places=2, null=True)
    payment_due_date = models.DateTimeField(null=True)
    update_timestamp = models.DateTimeField()

    def __str__(self):
        return ("%s : available balance %s" % (self.card_account_id, self.current))

    class Meta:
        verbose_name = "Latest Card Balance"
        verbose_name_plural = "Latest Card Balance"

    @classmethod
    def include_fields(cls):
        exclude_list = ['id','card_account_id']
        return [f.name for f in Card_account_balance._meta.fields if f.name not in exclude_list]

    @classmethod
    def latest_available_balance(cls, card_account_id):
        try:
            balance = Card_account_balance.objects.values("available").filter(card_account_id=card_account_id).latest('update_timestamp')
        except ObjectDoesNotExist:
            return ({'code': 201,'desc': 'Card account does not exist'})
        return balance

    @classmethod
    def latest_current_balance(cls, card_account_id):
        try:
            balance = Card_account_balance.objects.values("current").filter(card_account_id=card_account_id).latest('update_timestamp')
        except ObjectDoesNotExist:
            return ({'code': 201, 'desc': 'Card account does not exist'})
        return balance

    @classmethod
    def get_card_account_balances_update(cls, username):

        # get the correct url string for updates
        access_info = TL_info.url_access()

        # get all accounts and credentials for a given user
        account_list = Cards.get_card_accounts(username)

        # iterate over the tokens to get all information
        for i in range(0, len(account_list)):
            access_token = Token.get_access_token_one(account_list[i]['credentials_id'])
            token_phrase = "Bearer %s" % access_token
            headers = {'Authorization': token_phrase}
            url = "%s/%s/balance" % (access_info['card_url'], account_list[i]['card_account_id'])
            z = requests.get(url, headers=headers)

            # check API status code and if OK, iterate over the results and update records
            if z.status_code == 200:
                results = z.json()['results']
                new_results = results[0]
                try:
                    # if TL does not return the field, set it to None for Django sanity, this can be replaced once we develop a serialiser
                    for field in Account_balance.include_fields():
                        if field not in new_results.keys():
                            new_results[field] = None

                    # write the new records
                    card_balance = cls(
                        card_account_id = Cards.objects.get(card_account_id = account_list[i]['card_account_id']),
                        available = new_results['available'],
                        currency = new_results['currency'],
                        current = new_results['current'],
                        credit_limit = new_results['credit_limit'],
                        last_statement_balance = new_results['last_statement_balance'],
                        last_statement_date = new_results['last_statement_date'],
                        payment_due = new_results['payment_due'],
                        payment_due_date = new_results['payment_due_date'],
                        update_timestamp = new_results['update_timestamp']
                    )
                    card_balance.save()

                except:
                    raise Exception('Unknown db error')
            else:
                return ({'code': 400,
                         'desc': 'Truelayer Card Balance API failure. TL error code = %s and message = %s' % (
                             z.status_code, z.json()['error'])
                         })
        return ({'code': 200, 'desc': 'Success'})

class Card_account_trans(models.Model):
    card_account_id = models.ForeignKey(Cards, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=128,primary_key=True)
    timestamp = models.DateTimeField()
    description = models.TextField(null=True)
    transaction_type = models.CharField(max_length=50)
    transaction_category = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=13,decimal_places=2)
    currency = models.CharField(max_length=3)
    meta = models.TextField(null=True)

    class Meta:
        verbose_name = "Card Account Transactions"
        verbose_name_plural = "Card Account Transactions"
        get_latest_by = "timestamp"

    @classmethod
    def include_fields(cls):
        exclude_list = ['card_account_id','transaction_id']
        return [f.name for f in Card_account_trans._meta.fields if f.name not in exclude_list]

    @classmethod
    def get_card_account_trans(cls,username):

        # get the correct url string for info updates
        access_info = TL_info.url_access()

        # get all accounts and credentials for a given user
        account_list = Cards.get_card_accounts(username)

        # iterate over the tokens to get all information
        for i in range(0, len(account_list)):
            # establish the correct url string for each account
            access_token = Token.get_access_token_one(account_list[i]['credentials_id'])
            token_phrase = "Bearer %s" % access_token
            headers = {'Authorization': token_phrase}

            try: # trap for null recordsets
                latest = Card_account_trans.objects.values_list('timestamp').filter(card_account_id = account_list[i]['card_account_id']).latest('timestamp')
                f_date = latest[0].strftime("%Y-%m-%d")
            except ObjectDoesNotExist:
                f_date = (timezone.now() - timedelta(days=365)).strftime("%Y-%m-%d")

            t_date = timezone.now().strftime("%Y-%m-%d")

            url = "%s/%s/transactions?from=%s&to=%s" % (access_info['card_url'], account_list[i]['card_account_id'],f_date,t_date)
            z = requests.get(url, headers=headers)

            if z.status_code == 200:
                results = z.json()['results']

                # check for fields that are not provided so Django is happy (prefer NoSQL approach)
                include_fields = Card_account_trans.include_fields()

                # set the accoutn in advance so it is not called during looping
                account=Cards.objects.get(card_account_id = account_list[i]['card_account_id'])

                for i in range(0,len(results)):
                    new_results = results[i]

                    # check the include fields (keeping Django happy again)
                    for field in include_fields: # Todo refactor to a comprehension for speed
                        if field not in new_results.keys():
                            new_results[field] = None

                    # write the data out (no bulk adds in Django ... thank you django, let's add 1 by 1)
                    try:
                        account_trans = cls(
                            card_account_id=account,
                            transaction_id = new_results['transaction_id'],
                            timestamp = new_results['timestamp'],
                            description = new_results['description'],
                            transaction_type = new_results['transaction_type'],
                            transaction_category = new_results['transaction_category'],
                            amount = new_results['amount'],
                            currency = new_results['currency'],
                            meta = new_results['meta'],
                           )
                        account_trans.save()
                    except:
                        raise Exception('Unknown db error')
            else:
                return ({'code': 400,
                         'desc': 'Truelayer Card Transaction API failure. TL error code = %s and message = %s' % (
                             z.status_code, z.json()['error'])
                         })
        return ({'code': 200, 'desc': 'Success'})