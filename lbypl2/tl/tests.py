from django.test import TestCase
from .models import Providers

# Create your tests here.

# 1 - test for same UUID before and after update
# 2- test for 200 status and processing of updates
# 3 - test that token new has a model with field count -2 = json dict keys. \
# we add user_id and provider_id to the json so if it grows then the

class ProviderTests(TestCase):

    def one_provider_id(self):
        # Ensures there is only one entry per provider after the update procedure is run
        Providers.update_providers()
        max_count = Providers.objects.raw("select max(p_count) from\
         (select provider_id, count(provider_id) as p_count from tl_providers group by provider_id")
        self.assertEqual(1,max_count)

