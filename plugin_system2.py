import time

class StopwatchPlugin:
    def setup(self):
        print("StopwatchPlugin setup called!")

    def apply(self, callback):
        def wrapper(request, *args, **kwargs):
            start = time.time()
            result = callback(request, *args, **kwargs)
            end = time.time()
            request.headers['X-Exec-Time'] = str(end - start)
            return result
        return wrapper


class CapitalizePlugin:
    def setup(self):
        print("CapitalizePlugin setup called!")

    def apply(self, callback):
        def wrapper(request, *args, **kwargs):
            result = callback(request, *args, **kwargs)
            return result.capitalize()
        return wrapper


class InjectPlugin:
    def setup(self):
        print("InjectPlugin setup called!")

    def apply(self, callback):
        def wrapper(request, *args, **kwargs):
            kwargs.update({'foo': 'bar'})
            return callback(request, *args, **kwargs)
        return wrapper


class Pipeline:
    """
    Pipeline supports objects with `setup` and `apply` methods.

    Usage:
    pipeline = Pipeline([plugin1, plugin2, plugin3])
    wrapped_function = pipeline(original)
    result = wrapped_function(request, *args, **kwargs)
    """
    def __init__(self, plugins):
        self.plugins = plugins
        for plugin in self.plugins:
            if hasattr(plugin, "setup") and callable(plugin.setup):
                plugin.setup()  # Initialize or configure the plugin

    def __call__(self, func):
        # Apply plugins sequentially to wrap the original function
        for plugin in reversed(self.plugins):
            func = plugin.apply(func)  # Each plugin wraps the previous function
        return func


# Mock request object
class Request:
    def __init__(self):
        self.headers = {}

# Original function to be wrapped
def original(request, *args, **kwargs):
    return "hello world"

# Create plugins
stopwatch_plugin = StopwatchPlugin()
capitalize_plugin = CapitalizePlugin()
inject_plugin = InjectPlugin()

# Create a pipeline with the plugins
pipeline = Pipeline([stopwatch_plugin, capitalize_plugin, inject_plugin])

# Apply the pipeline to the original function
wrapped_function = pipeline(original)

# Create a mock request object
request = Request()

# Call the wrapped function with the request object
result = wrapped_function(request)

# Outputs
print(result)  # "Hello world" (capitalized)
print(request.headers)  # Contains the execution time in 'X-Exec-Time'
