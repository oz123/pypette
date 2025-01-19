import json
import time
from wsgiref.simple_server import make_server
from datetime import datetime, date

from pypette import PyPette, static_file

class DateTimeISOEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

app = PyPette(json_encoder=DateTimeISOEncoder)

def stopwatch(callback):
    def wrapper(request, *args, **kwargs):
        start = time.time()
        result = callback(request, *args, **kwargs)
        end = time.time()
        print(f'X-Exec-Time {str(end - start)}')
        return result
    return wrapper

app.install(stopwatch)

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

@app.route('/fancy')
def view_with_template(request):
    return app.templates.load('base.html').render({
        "user_name": "Admin",
        "is_admin": True,
        "hobbies": ["Reading", "Cooking", "Cycling"],
        "current_year": 2024,
        "format_price": lambda x: x.upper(),
        })

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
