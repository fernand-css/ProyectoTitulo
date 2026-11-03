"""Verificación HTTP aislada de la spec 02; solo datos sintéticos y correo en memoria."""

import http.cookiejar, io, json, logging, os, re, secrets, sys, tempfile, threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, urljoin
from urllib.request import build_opener, HTTPCookieProcessor, Request
from wsgiref.simple_server import make_server, WSGIRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.update(DJANGO_SETTINGS_MODULE='cesfam.settings', SECRET_KEY=secrets.token_urlsafe(48), DEBUG='True', ALLOWED_HOSTS='127.0.0.1,localhost')
from django.conf import settings
qa_root = Path(tempfile.mkdtemp(prefix='cesfam-spec02-')).resolve()
db = qa_root / 'qa.sqlite3'
settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(db)}
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.core.handlers.wsgi import WSGIHandler
from django.contrib.staticfiles.handlers import StaticFilesHandler
from coreapp.models import RegistroAuditoria
from coreapp.roles import TECNICO, ENCARGADO

server = None
thread = None
try:
    assert Path(connections['default'].settings_dict['NAME']).resolve() == db
    call_command('migrate', verbosity=0, interactive=False)
    migraciones = MigrationRecorder.Migration.objects.count()
    clave = 'QA-' + secrets.token_urlsafe(24) + '9!'
    os.environ['CESFAM_DEMO_PASSWORD'] = clave
    call_command('crear_usuarios_demo', noinput=True, stdout=io.StringIO())
    Usuario = get_user_model()
    hashes = dict(Usuario.objects.values_list('username', 'password'))
    call_command('crear_usuarios_demo', noinput=True, stdout=io.StringIO())
    assert dict(Usuario.objects.values_list('username', 'password')) == hashes
    admin = Usuario.objects.create_superuser(username='qa_admin_sintetico', password=clave)
    logging.getLogger('django.request').setLevel(logging.CRITICAL)
    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *args):
            pass
    server = make_server('127.0.0.1', 0, StaticFilesHandler(WSGIHandler()), handler_class=QuietHandler)
    base = 'http://127.0.0.1:' + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    class NavegacionHTTP:
        def __init__(self):
            self.jar = http.cookiejar.CookieJar()
            self.opener = build_opener(HTTPCookieProcessor(self.jar))
        def pedir(self, ruta, datos=None):
            url = urljoin(base, ruta)
            if datos is not None:
                datos = dict(datos)
                csrf = next((c.value for c in self.jar if c.name == 'csrftoken'), '')
                datos['csrfmiddlewaretoken'] = csrf
                req = Request(url, data=urlencode(datos).encode(), headers={'Referer': url})
            else:
                req = Request(url)
            try:
                with self.opener.open(req, timeout=10) as r:
                    return r.status, r.read().decode('utf-8'), urlsplit(r.url).path
            except HTTPError as r:
                return r.code, r.read().decode('utf-8'), urlsplit(r.url).path
        def login(self, usuario, password):
            self.pedir('/usuarios/entrar/')
            codigo, _, ruta = self.pedir('/usuarios/entrar/', {'username': usuario, 'password': password})
            assert codigo == 200 and ruta == '/'
    qf = NavegacionHTTP()
    qf.login('demo_qf', clave)
    assert qf.pedir('/usuarios/gestion/')[0] == 200
    qf.pedir('/usuarios/gestion/nuevo/')
    codigo, _, ruta = qf.pedir('/usuarios/gestion/nuevo/', dict(username='qa_operador_http', first_name='Persona', last_name='Sintetica', email='qa.operador@example.invalid', rol=TECNICO, password1=clave, password2=clave))
    assert codigo == 200 and ruta == '/usuarios/gestion/'
    objetivo = Usuario.objects.get(username='qa_operador_http')
    enlace = re.search(r'https?://\S+', mail.outbox[-1].body).group()
    anonimo = NavegacionHTTP()
    assert anonimo.pedir(enlace)[0] == 200
    assert anonimo.pedir(enlace, {})[0] == 200
    objetivo.refresh_from_db()
    assert objetivo.email == 'qa.operador@example.invalid'
    editar = f'/usuarios/gestion/{objetivo.pk}/editar/'
    qf.pedir(editar)
    assert qf.pedir(editar, dict(first_name='Actualizada', last_name='Sintetica', email=objetivo.email, rol=ENCARGADO))[0] == 200
    personal = NavegacionHTTP()
    personal.login(objetivo.username, clave)
    assert personal.pedir('/usuarios/perfil/')[0] == 200
    assert personal.pedir('/usuarios/gestion/')[0] == 403
    estado = f'/usuarios/gestion/{objetivo.pk}/estado/'
    assert qf.pedir(estado, {'activo':'0'})[0] == 200
    assert personal.pedir('/')[2] == '/usuarios/entrar/'
    assert qf.pedir(estado, {'activo':'1'})[0] == 200
    raiz = NavegacionHTTP()
    raiz.login(admin.username, clave)
    codigo, cuerpo, _ = raiz.pedir('/admin/coreapp/registroauditoria/')
    assert codigo == 200 and objetivo.email not in cuerpo
    registro = RegistroAuditoria.objects.filter(objeto_id=str(objetivo.pk)).first()
    assert raiz.pedir(f'/admin/coreapp/registroauditoria/{registro.pk}/change/', {'accion':'alterada'})[0] == 403
    recuperar = NavegacionHTTP()
    recuperar.pedir('/usuarios/clave/recuperar/')
    assert recuperar.pedir('/usuarios/clave/recuperar/', {'username':objetivo.username,'email':objetivo.email})[2] == '/usuarios/clave/enviada/'
    enlace_clave = re.search(r'https?://\S+', mail.outbox[-1].body).group()
    codigo, _, ruta = recuperar.pedir(enlace_clave)
    assert codigo == 200 and 'set-password' in ruta
    nueva = 'QA-' + secrets.token_urlsafe(24) + '7!'
    assert recuperar.pedir(ruta, {'new_password1':nueva,'new_password2':nueva})[2] == '/usuarios/clave/lista/'
    objetivo.refresh_from_db()
    assert objetivo.check_password(nueva) and not objetivo.check_password(clave)
    codigo, cuerpo, _ = recuperar.pedir(enlace_clave)
    assert codigo == 200 and 'El enlace no es válido' in cuerpo
    assert qf.pedir('/static/css/base.css')[0] == 200
    assert qf.pedir('/static/js/alpine.min.js')[0] == 200
    assert qf.pedir('/sw.js')[0] == 200
    print(json.dumps({'migraciones_aplicadas_en_sqlite_nueva':migraciones,'repeticion_demo_conserva_hashes':True,'http_real':'login QF, alta, verificacion, cambio de rol, desactivacion/reactivacion, restricciones, auditoria y recuperacion aprobados','estaticos_y_service_worker':'200','correo':'solo memoria','base_local_del_proyecto':'sin modificar'},ensure_ascii=False))
finally:
    if server:
        server.shutdown()
        server.server_close()
    if thread:
        thread.join(timeout=5)
    connections.close_all()
    assert qa_root.parent == Path(tempfile.gettempdir()).resolve() and qa_root.name.startswith('cesfam-spec02-')
    for nombre in ('qa.sqlite3','qa.sqlite3-journal','qa.sqlite3-wal','qa.sqlite3-shm'):
        archivo = qa_root / nombre
        assert archivo.resolve().parent == qa_root
        archivo.unlink(missing_ok=True)
    qa_root.rmdir()
