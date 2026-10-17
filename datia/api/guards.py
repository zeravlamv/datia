from functools import wraps

from django.http import JsonResponse


def login_required_json(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
        return view(request, *args, **kwargs)
    return wrapped
