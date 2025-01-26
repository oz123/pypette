PyPette - A drop of WSGI
========================

PyPette is a nano WSGI framework inspired by itty and bottle.py.
It aims to be really small, yet full featured and easy to understand.

Despite its small size you should be able to build small or large applications
with it. It includes:
 
 * Builtin the Templite template engine with Jinja2 like syntax.
 * Plugin system, which allows extending it
 * HTTP Request parsing.
 * Automatic JSON responses.
 * Streaming file uploads.
 * Static file serving.
 * Application mounting for building composable apps.
 * Familiar decorator `@app.route` syntax.

Here is an example:

```
app = PyPette()

@app.route("/hello/")
@app.route("/hello/:name")
def hello_name(request, name="world"):
    return f"hello {name}"

@app.route('/fancy')
def view_with_template_2(request):
    return template('base.html').render(_get_vars())

@app.route("/api/")
def hello_json(request):
    return {"something": "you can json serialize ...",
            "today is": date.today(), "now": datetime.now()}
```
