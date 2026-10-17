import uuid
import logging
import threading

# Thread-local storage for Trace ID
_thread_locals = threading.local()

def get_current_trace_id():
    return getattr(_thread_locals, 'trace_id', 'no-trace-id')

class TraceIDMiddleware:
    """
    Middleware to inject a unique Trace ID into every request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = request.headers.get('X-Trace-ID', str(uuid.uuid4()))
        _thread_locals.trace_id = trace_id
        
        request.trace_id = trace_id
        
        response = self.get_response(request)
        
        response['X-Trace-ID'] = trace_id
        return response

class TraceIDFilter(logging.Filter):
    """
    Logging filter to inject the Trace ID into log records.
    """
    def filter(self, record):
        record.trace_id = get_current_trace_id()
        return True
