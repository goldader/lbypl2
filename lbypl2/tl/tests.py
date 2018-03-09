from django.test import TestCase
from .models import Providers

# Create your tests here.

# todo 1 - test for same UUID before and after update
# todo 2 - test for 200 status and processing of updates
# todo 3 - test that token new has a model with field count -2 = json dict keys.
# todo 4 - test that there is only 1 token per user / provider_id combination
# todo 5 - test that multiple addresses does not break User_info
# todo 6 - test that multiple phones or emails does not break User_info
# todo 7 - test that json with extra shit doesn't break user_info
# todo 8 - test that a bum api forces user_info to fail nicely

class ProviderTests(TestCase):

    def one_provider_id(self):
        # Ensures there is only one entry per provider after the update procedure is run
        Providers.update_providers()
        max_count = Providers.objects.raw("select max(p_count) from\
         (select provider_id, count(provider_id) as p_count from tl_providers group by provider_id")
        self.assertEqual(1,max_count)

