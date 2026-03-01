from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE'])

        # якщо cookie з токеном відсутні
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            # Повертаємо кортеж (User, Token), як вимагає DRF
            return self.get_user(validated_token), validated_token

        # Якщо токен помилковий/відсутній - позначити користувача як аноніма (AllowAny)
        except (InvalidToken, TokenError):
            return None

