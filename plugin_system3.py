class Pipeline:
    """
    Pipeline supports both simple callables (like decorators) and objects with `setup` and `apply` methods.

    Usage:
    pipeline = Pipeline([plugin1, plugin2, callable_decorator, plugin3])
    wrapped_function = pipeline(original)
    result = wrapped_function(request, *args, **kwargs)
    """
    def __init__(self, plugins):
        self.plugins = plugins
        for plugin in self.plugins:
            if hasattr(plugin, "setup") and callable(plugin.setup):
                plugin.setup()  # Call setup if the plugin is an object with a setup method

    def __call__(self, func):
        # Apply all plugins (either callables or objects) to the function
        for plugin in reversed(self.plugins):
            if hasattr(plugin, "apply") and callable(plugin.apply):
                func = plugin.apply(func)  # Use the plugin's apply method
            elif callable(plugin):
                func = plugin(func)  # Treat as a simple decorator
            else:
                raise TypeError(f"Invalid plugin: {plugin}. Must be callable or have an 'apply' method.")
        return func

import time


def stopwatch(callback):
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

# Mock request object
class Request:
    def __init__(self):
        self.headers = {}

def original(request, *args, **kwargs):
    return "hello world"

# Create plugins and decorators
capitalize_plugin = CapitalizePlugin()
inject = InjectPlugin()
# Create a pipeline mixing plugins and callables
pipeline = Pipeline([stopwatch, CapitalizePlugin(), inject])

# Apply the pipeline to the original function
wrapped_function = pipeline(original)

# Create a mock request object
request = Request()

# Call the wrapped function
result = wrapped_function(request)

# Outputs
print(result)  # "Hello world" (capitalized)
print(request.headers)  # Contains the execution time in 'X-Exec-Time'
