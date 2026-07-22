# accounts/schema.py

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class StudentJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.StudentJWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }