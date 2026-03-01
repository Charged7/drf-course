from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CustomJWTScheme(OpenApiAuthenticationExtension):
    target_class = 'api.authentication.CustomJWTAuthentication'
    name = 'jwtCookieAuth'  # Унікальне ім'я

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'cookie',
            'name': 'access_token',  # Має збігатися з AUTH_COOKIE у твоїх settings
        }