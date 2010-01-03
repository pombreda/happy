import unittest

class TestFormLoginMiddleware(unittest.TestCase):
    def _make_one(self, app, **kw):
        from happy.login import FormLoginMiddleware
        return FormLoginMiddleware(
            app,
            DummyPasswordBroker(),
            DummyPrincipalsBroker(),
            DummyCredentialBroker(),
            **kw
        )

    def test_login_logout(self):
        from webob import Request
        fut = self._make_one(dummy_app)

        request = Request.blank('/')
        response = fut(request)
        self.assertEqual(response.remote_user, None)
        self.assertEqual(response.principals, None)

        request = Request.blank('/login')
        response = fut(request)
        self.failUnless('login' in response.body)

        request = Request.blank('/login', POST={
            'login': 'chris@example.com',
            'password': '12345678'
            }
        )
        response = fut(request)
        credential = get_cookie(response, 'happy.login')
        self.failUnless(credential)
        self.assertEqual(response.location, 'http://localhost')

        request = Request.blank('/')
        request.cookies['happy.login'] = credential
        response = fut(request)
        self.assertEqual(response.remote_user, 'user-1234')
        self.assertEqual(response.principals,
                         ['user-1234', 'group.Administrators'])

        request = Request.blank('/logout')
        request.cookies['happy.login'] = credential
        response = fut(request)
        credential = get_cookie(response, 'happy.login')
        self.failIf(credential)
        self.assertEqual(response.location, 'http://localhost')

        request = Request.blank('/')
        request.cookies['happy.login'] = credential
        response = fut(request)
        self.assertEqual(response.remote_user, None)
        self.assertEqual(response.principals, None)

    def test_custom_form_template(self):
        def dummy_template(**kw):
            assert kw['login'] ==  'chris'
            assert kw['redirect_to'] == 'foo'
            assert kw['status_msg'] == 'message'
            return 'Howdy!'

        from webob import Request
        fut = self._make_one(dummy_app, form_template=dummy_template)
        request = Request.blank(
            '/login?status_msg=message&redirect_to=foo&login=chris'
        )
        self.assertEqual(fut(request).body, 'Howdy!')

    def test_login_bad_login(self):
        from webob import Request
        fut = self._make_one(dummy_app)
        request = Request.blank(
            '/login',
            POST=dict(login='chris', password='12345678')
        )
        body = fut(request).body
        self.failUnless('Bad username or password' in body, body)

    def test_login_bad_password(self):
        from webob import Request
        fut = self._make_one(dummy_app)
        request = Request.blank(
            '/login',
            POST=dict(login='chris@example.com', password='123456789')
        )
        body = fut(request).body
        self.failUnless('Bad username or password' in body, body)

    def test_redirect_401(self):
        def app(request):
            return DummyResponse(401)

        from webob import Request
        fut = self._make_one(app)
        request = Request.blank('/')
        self.assertEqual(fut(request).location, 'http://localhost/login')

    def test_dont_redirect_401(self):
        def app(request):
            return DummyResponse(401)

        from webob import Request
        fut = self._make_one(app, redirect_401=False)
        request = Request.blank('/')
        self.assertEqual(fut(request).status_int, 401)

    def test_redirect_403(self):
        def app(request):
            return DummyResponse(403)

        from webob import Request
        fut = self._make_one(app, redirect_403=True)
        request = Request.blank('/')
        self.assertEqual(fut(request).location, 'http://localhost/login')

    def test_dont_redirect_403(self):
        def app(request):
            return DummyResponse(403)

        from webob import Request
        fut = self._make_one(app)
        request = Request.blank('/')
        self.assertEqual(fut(request).status_int, 403)


class DummyPasswordBroker(object):
    _passwords = {
        'chris@example.com': '12345678',
    }

    def check_password(self, login, password):
        return login in self._passwords and self._passwords[login] == password

class DummyPrincipalsBroker(object):
    _principals = {
        'chris@example.com': ['user-1234', 'group.Administrators']
    }

    def get_userid(self, login):
        return self._principals[login][0]

    def get_principals(self, login):
        return self._principals[login]

class DummyCredentialBroker(object):
    def __init__(self):
        self._credentials = {}

    def login(self, login):
        import uuid
        credential = str(uuid.uuid4())
        self._credentials[credential] = login
        return credential

    def logout(self, credential):
        del self._credentials[credential]

    def get_login(self, credential):
        return self._credentials.get(credential, None)

class DummyResponse(object):
    def __init__(self, status_int=200):
        self.status_int = status_int

def dummy_app(request):
    response = DummyResponse()
    response.remote_user = request.remote_user
    response.principals = getattr(
        request, 'authenticated_principals', None
    )
    return response

def get_cookie(response, cookie_name):
    for k, v in response.headers.items():
        if k == 'Set-Cookie':
            name, value = v.split(';')[0].split('=')
            if name == cookie_name:
                return value