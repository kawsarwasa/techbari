from django.conf import settings
from django.test.runner import DiscoverRunner


class TechBariTestRunner(DiscoverRunner):
    """Keep pre-RBAC business tests focused on business behavior.

    The v2.5 StaffAccessTests explicitly override STAFF_AUTH_ENABLED=True and
    therefore exercise the real authentication/authorization boundary. Legacy
    module tests predate staff authentication and continue to test their CRUD,
    accounting and transaction semantics without needing authentication setup.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._staff_auth_enabled = getattr(settings, "STAFF_AUTH_ENABLED", True)
        settings.STAFF_AUTH_ENABLED = False

    def teardown_test_environment(self, **kwargs):
        settings.STAFF_AUTH_ENABLED = self._staff_auth_enabled
        super().teardown_test_environment(**kwargs)
