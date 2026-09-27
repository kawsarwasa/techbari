from django.test.runner import DiscoverRunner


class TechBariTestRunner(DiscoverRunner):
    """Run tests with the same staff authentication boundary enabled by default."""
