from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(
    summary="Отримання access та refresh токенів",
    responses={200: inline_serializer(
            name='TokenAccessResponse',
            fields={
                'access': serializers.CharField(),
                'refresh': serializers.CharField(),
            }
        ),
    },
    tags=["Auth"]
)
class CookieTokenObtainPairView(TokenObtainPairView):
    """Після отримання токенів кладемо їх в cookies"""

    def post(self, request, *args, **kwargs):
        # Викликаємо батьківський метод, який валідує поля і надсилає токени
        response = super().post(request, *args, **kwargs)

        # Отримуємо токени з JSON відповіді
        access_token = response.data.get('access')
        refresh_token = response.data.get('refresh')

        # Кладемо токени in cookies
        response.set_cookie(
            key=settings.SIMPLE_JWT['AUTH_COOKIE'],
            value=access_token,
            httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
            path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
        )

        response.set_cookie(
            key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
            value=refresh_token,
            httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
            path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
        )

        return response


@extend_schema(
    summary="Оновлення access token",
    request=None, # Важливо: приховує поле 'refresh' з UI запиту
    responses={200: inline_serializer(
            name='TokenRefreshResponse',
            fields={
                'access': serializers.CharField(),
                'refresh': serializers.CharField(),
            }
        )}, # Повертає "No Content"
    tags=["Auth"]
)
class CookieTokenRefreshView(TokenRefreshView):
    """Отримання access токена через refresh токен з cookies"""

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        # щоб в api/token/refresh не треба було додавати refresh токен в body, а брати його з cookies
        if refresh_token:
            data = request.data.copy()
            data['refresh'] = refresh_token
            request._full_data = data

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                value=access_token,
                httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
            )
            if refresh_token:
                response.set_cookie(
                    key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
                    value=refresh_token,
                    httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                    secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                    samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                    path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
                )
        return response


@extend_schema(
    summary="Вихід з системи",
    request=None, # Logout зазвичай не потребує тіла запиту
    responses={204: None}, # Повертає "No Content"
    tags=["Auth"]
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])

            if refresh_token:
                # Додаємо токен в Blacklist
                token = RefreshToken(refresh_token)
                token.blacklist()

            response = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
            response.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE'])
            response.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])

            return response
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
