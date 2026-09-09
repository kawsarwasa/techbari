class ProductionSecurityHeadersMiddleware:
    """Add low-risk browser security headers without relying on the web server."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.setdefault("Cross-Origin-Resource-Policy", "same-site")
        return response
