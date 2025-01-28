import re

from http.client import HTTPResponse
from typing import List, Union, Pattern

from pypette import PyPette


class CORSPlugin:
    def __init__(self, origins: Union[List[str], List[Pattern], str], app: PyPette):
        app.add_route("/", lambda x: x, method="OPTIONS")
        
        # Convert single string to list for consistent handling
        if isinstance(origins, str):
            origins = [origins]
            
        # Convert string patterns to regex patterns
        self.origins = []
        for origin in origins:
            if isinstance(origin, str):
                if '*' in origin:
                    # Convert glob patterns to regex
                    pattern = origin.replace('.', r'\.').replace('*', r'.*')
                    self.origins.append(re.compile(pattern))
                else:
                    self.origins.append(origin)
            else:
                self.origins.append(origin)

    def is_origin_allowed(self, request_origin: str) -> bool:
        if not request_origin:
            return False
            
        for origin in self.origins:
            if isinstance(origin, Pattern):
                if origin.match(request_origin):
                    return True
            elif origin == '*' or origin == request_origin:
                return True
        return False

    def __call__(self, callback):
        def wrapper(request, *args, **kwargs):
            response = callback(request, *args, **kwargs)

            if isinstance(response, str):
                response = HTTPResponse(body=response)

            request_origin = request.headers.get('Origin')
            
            if self.is_origin_allowed(request_origin):
                # If origin is allowed, reflect the requesting origin
                response.headers['Access-Control-Allow-Origin'] = request_origin
            elif '*' in self.origins:
                # If wildcard is allowed, send wildcard
                response.headers['Access-Control-Allow-Origin'] = '*'
                
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
            
            # Add Vary header when using dynamic origins
            if '*' not in self.origins:
                response.headers['Vary'] = 'Origin'
                
            return response

        return wrapper

