import time

class Pipeline:
    """
    # Usage:
    pipeline = Pipeline([stopwatch, capitalize, inject])
    wrapped_function = pipeline(original)
    result = wrapped_function(request, *args, **kwargs)
    """
    def __init__(self, functions):
        self.functions = functions

    def __call__(self, func):
        # Dynamically wrap the function with all decorators in reverse order
        for wrapper in reversed(self.functions):
            func = wrapper(func)
        return func


def stopwatch(callback):
    def wrapper(request, *args, **kwargs):
        start = time.time()
        result = callback(request, *args, **kwargs)
        end = time.time()
        request.headers['X-Exec-Time'] = str(end - start)
        return result
    return wrapper

def capitalize(callback):
    def wrapper(request, *args, **kwargs):
        result = callback(request, *args, **kwargs)
        return result.upper()
    return wrapper

def inject(callback):
    def wrapper(request, *args, **kwargs):
        kwargs.update({'foo': 'bar'})
        return callback(request, *args, **kwargs)
    return wrapper


# Mock request object
class Request:
    def __init__(self):
        self.headers = {}

# Original function to be wrapped
def original(request, *args, **kwargs):
    return "hello world"

# Create a pipeline with the desired decorators
pipeline = Pipeline([stopwatch, capitalize, inject])

# Apply the pipeline to the original function
wrapped_function = pipeline(original)

# Create a mock request object
request = Request()

# Call the wrapped function with the request object
result = wrapped_function(request)

# Outputs
print(result)  # "Hello world" (capitalized)
print(request.headers)  # Contains the execution time in 'X-Exec-Time'
