from .services import CAMPAIGN_COOKIE, CAMPAIGN_COOKIE_MAX_AGE, capture_campaign_request, encode_campaign_cookie


class CampaignTrackingMiddleware:
    """Capture explicit campaign/utm_campaign landings without requiring Django sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        capture = capture_campaign_request(request)
        response = self.get_response(request)
        if capture:
            campaign, tracking_token = capture
            response.set_cookie(CAMPAIGN_COOKIE, encode_campaign_cookie(campaign, tracking_token), max_age=CAMPAIGN_COOKIE_MAX_AGE, httponly=True, secure=request.is_secure(), samesite="Lax")
        return response
