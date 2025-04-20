import json
import time
from wsgiref.simple_server import make_server
from datetime import datetime, date

from pypette import PyPette, static_file, HTTPResponse

class DateTimeISOEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

app = PyPette(json_encoder=DateTimeISOEncoder)
template = lambda tname: app.templates.load(tname)

def stopwatch(callback):
    def wrapper(request, *args, **kwargs):
        start = time.time()
        result = callback(request, *args, **kwargs)
        end = time.time()
        print(request)
        print(f'X-Exec-Time {str(end - start)}')
        return result
    return wrapper


class CORSPlugin:
    """Plugin to handle Cross Origin Resource Sharing
    Allows just one origin.

    For a more sophisticated plugin see the plugins directory
    """
    def __init__(self, origin: str, app: PyPette):
        app.add_route("/", lambda x: x, method="OPTIONS")
        self.origin = origin

    def __call__(self, callback):
        def wrapper(request, *args, **kwargs):
            response = callback(request, *args, **kwargs)

            if isinstance(response, str):
               response = HTTPResponse(body=response)

            response.headers['Access-Control-Allow-Origin'] = self.origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
            return response

        return wrapper

cors = CORSPlugin("*", app)
app.install(stopwatch)
app.install(cors)

def hello(request):
    return "hello world"

@app.route("/hello/")
@app.route("/hello/:name")
def hello_name(request, name="world"):
    return f"hello {name}"

@app.route("/api/")
def hello_json(request):
    return {"something": "you can json serialize ...",
            "today is": date.today(), "now": datetime.now()}

def _get_vars():
    return {
        "user_name": "Admin",
        "is_admin": True,
        "hobbies": ["Reading", "Cooking", "Cycling"],
        "current_year": date.today().year,
        "upper": lambda x: x.upper(),
        }

@app.route('/fancy')
def view_with_template(request):
    return app.templates.load('base.html').render(_get_vars())

@app.route('/fancy2')
def view_with_template_2(request):
    return template('base.html').render(_get_vars())


@app.route('/upload', method='POST')
def upload(request):
    test = request.files['test.txt'] 
    content = test['content']
    return {"content": content.decode()}

@app.route("/static/:filename", method='GET')
def static(request, filename):
    rv = static_file(request, filename, 'views/static')
    return rv

@app.route("/trigger", method="GET")
def trigger_error(request):
    """we really should not do this..."""
    1/0

app.add_route("/", hello)


app2 = PyPette()

@app2.route("/greeter")
@app2.route("/greeter/:name")
def greeter(request, name="world"):
    return f"Hello {name}!"

app.mount("/app2", app2)

app.resolver.print_trie()

httpd = make_server('', 8000, app)
print("Serving on port 8000...")

# Serve until process is killed
httpd.serve_forever()
