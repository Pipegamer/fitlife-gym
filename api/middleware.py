import time
from django.utils.deprecation import MiddlewareMixin

class AuditSLAMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = time.time()

    def process_response(self, request, response):
        if hasattr(request, '_start_time'):
            latencia_ms = round((time.time() - request._start_time) * 1000, 2)
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            user = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'Anonimo'
            
            linea = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] IP={ip} USER={user} METHOD={request.method} PATH={request.path} STATUS={response.status_code} LATENCIA={latencia_ms}ms\n"
            try:
                with open('access_log.log', 'a', encoding='utf-8') as f:
                    f.write(linea)
            except Exception:
                pass
        return response
