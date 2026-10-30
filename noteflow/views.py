import time
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """
    Health check endpoint to keep the server and database awake (prevent Supabase sleep mode).
    Executes a lightweight query on PostgreSQL.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Health Check & DB Keep-Alive",
        description="Checks database connectivity and responds with timestamp and latency to keep Supabase awake.",
        responses={200: dict},
    )
    def get(self, request, *args, **kwargs):
        start_time = time.time()
        db_status = "healthy"
        error_message = None

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
        except Exception as e:
            db_status = "unhealthy"
            error_message = str(e)

        latency_ms = round((time.time() - start_time) * 1000, 2)

        data = {
            "status": "online" if db_status == "healthy" else "degraded",
            "database": db_status,
            "database_engine": connection.vendor,
            "latency_ms": latency_ms,
            "timestamp": timezone.now().isoformat(),
        }

        if error_message:
            data["error"] = error_message
            return Response(data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(data, status=status.HTTP_200_OK)

