from wsgiref.simple_server import make_server

import peewee as pw
from pypette import PyPette


db = pw.SqliteDatabase(':memory:')


class People(pw.Model):
    name = pw.CharField()
    birthday = pw.DateField()

    class Meta:
        database = db

db.create_tables([People])

People(name="Albert Einstein", birthday="1879-03-14").save()
People(name="Richard Feynman", birthday="1918-05-11").save()

myapp = PyPette()


@myapp.route("/hello")
def hello(request):
    return "hello"


from pypette_admin import admin

admin.register_model(People)

myapp.mount("/admin", admin)

httpd = make_server('', 8000, myapp)
print("Serving on port 8000...")

myapp.resolver.print_trie()

# Serve until process is killed
httpd.serve_forever()
