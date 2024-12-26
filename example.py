import json
from wsgiref.simple_server import make_server
from datetime import datetime, date

from pypette import PyPette, static_file

class DateTimeISOEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

app = PyPette(json_encoder=DateTimeISOEncoder)

def hello(request):
    return "hello world"

@app.route("/hello/:name")
def hello_name(request, name):
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
    return static_file(request, filename, 'views/static')

app.add_route("/", hello)

app.resolver.print_trie()
httpd = make_server('', 8000, app)
print("Serving on port 8000...")

# Serve until process is killed
httpd.serve_forever()
