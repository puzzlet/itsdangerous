import time
import pickle
import hashlib
import unittest
from datetime import datetime
import itsdangerous as idmod


class SerializerTestCase(unittest.TestCase):
    serializer_class = idmod.Serializer

    def make_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    def test_dumps_loads(self):
        objects = (['a', 'list'], b'a byte string', 'a unicode string \u2019',
                   {'a': 'dictionary'}, 42, 42.5)
        s = self.make_serializer('Test')
        for o in objects:
            value = s.dumps(o)
            self.assertNotEqual(o, value)
            self.assertEqual(o, s.loads(value))

    def test_decode_detects_tampering(self):
        transforms = (
            lambda s: s.upper(),
            lambda s: s + b'a',
            lambda s: b'a' + s[1:],
            lambda s: s.replace(b'.', b''),
        )
        value = {
            'foo': 'bar',
            'baz': 1,
        }
        s = self.make_serializer('Test')
        encoded = s.dumps(value)
        self.assertEqual(value, s.loads(encoded))
        for transform in transforms:
            self.assertRaises(
                idmod.BadSignature, s.loads, transform(encoded))

    def test_accepts_unicode(self):
        objects = (['a', 'list'], b'a byte string', 'a unicode string \u2019',
                   {'a': 'dictionary'}, 42, 42.5)
        s = self.make_serializer('Test')
        for o in objects:
            value = s.dumps(o)
            self.assertNotEqual(o, value)
            self.assertEqual(o, s.loads(value))

    def test_exception_attributes(self):
        secret_key = 'predictable-key'
        value = 'hello'

        s = self.make_serializer(secret_key)
        ts = s.dumps(value)

        try:
            s.loads(ts + b'x')
        except idmod.BadSignature as e:
            self.assertEqual(e.payload, ts.rsplit(b'.', 1)[0])
            self.assertEqual(s.load_payload(e.payload), value)
        else:
            self.fail('Did not get bad signature')

    def test_unsafe_load(self):
        secret_key = 'predictable-key'
        value = 'hello'

        s = self.make_serializer(secret_key)
        ts = s.dumps(value)
        self.assertEqual(s.loads_unsafe(ts), (True, 'hello'))
        self.assertEqual(s.loads_unsafe(ts, salt='modified'), (False, 'hello'))

    def test_load_unsafe_with_unicode_strings(self):
        secret_key = 'predictable-key'
        value = 'hello'

        s = self.make_serializer(secret_key)
        ts = s.dumps(value)
        self.assertEqual(s.loads_unsafe(ts), (True, 'hello'))
        self.assertEqual(s.loads_unsafe(ts, salt='modified'), (False, 'hello'))

        try:
            s.loads(ts, salt='modified')
        except idmod.BadSignature as e:
            self.assertEqual(s.load_payload(e.payload), 'hello')

    def test_signer_kwargs(self):
        secret_key = 'predictable-key'
        value = 'hello'
        s = self.make_serializer(secret_key, signer_kwargs=dict(
            digest_method=hashlib.md5,
            key_derivation='hmac'
        ))
        ts = s.dumps(value)
        self.assertEqual(s.loads(ts), 'hello')


class TimedSerializerTestCase(SerializerTestCase):
    serializer_class = idmod.TimedSerializer

    def setUp(self):
        self._time = time.time
        time.time = lambda: idmod.EPOCH

    def tearDown(self):
        time.time = self._time

    def test_decode_with_timeout(self):
        secret_key = 'predictable-key'
        value = 'hello'

        s = self.make_serializer(secret_key)
        ts = s.dumps(value)
        self.assertNotEqual(ts, idmod.Serializer(secret_key).dumps(value))

        self.assertEqual(s.loads(ts), value)
        time.time = lambda: idmod.EPOCH + 10
        self.assertEqual(s.loads(ts, max_age=11), value)
        self.assertEqual(s.loads(ts, max_age=10), value)
        self.assertRaises(
            idmod.SignatureExpired, s.loads, ts, max_age=9)

    def test_decode_return_timestamp(self):
        secret_key = 'predictable-key'
        value = 'hello'

        s = self.make_serializer(secret_key)
        ts = s.dumps(value)
        loaded, timestamp = s.loads(ts, return_timestamp=True)
        self.assertEqual(loaded, value)
        self.assertEqual(timestamp, datetime.utcfromtimestamp(time.time()))

    def test_exception_attributes(self):
        secret_key = 'predictable-key'
        value = 'hello'

        s = self.make_serializer(secret_key)
        ts = s.dumps(value)
        try:
            s.loads(ts, max_age=-1)
        except idmod.SignatureExpired as e:
            self.assertEqual(e.date_signed,
                datetime.utcfromtimestamp(time.time()))
            self.assertEqual(e.payload, ts.rsplit(b'.', 2)[0])
            self.assertEqual(s.load_payload(e.payload), value)
        else:
            self.fail('Did not get expiration')


class URLSafeSerializerMixin(object):

    def test_is_base62(self):
        allowed = frozenset(b'0123456789abcdefghijklmnopqrstuvwxyz' +
                            b'ABCDEFGHIJKLMNOPQRSTUVWXYZ_-.')
        objects = (['a', 'list'], b'a byte string', 'a unicode string \u2019',
                   {'a': 'dictionary'}, 42, 42.5)
        s = self.make_serializer('Test')
        for o in objects:
            value = s.dumps(o)
            self.assertTrue(set(value).issubset(set(allowed)))
            self.assertNotEqual(o, value)
            self.assertEqual(o, s.loads(value))

    def test_invalid_base64_does_not_fail_load_payload(self):
        s = idmod.URLSafeSerializer('aha!')
        self.assertRaises(idmod.BadPayload, s.load_payload, 'kZ4m3du844lIN')


class PickleSerializerMixin(object):

    def make_serializer(self, *args, **kwargs):
        kwargs.setdefault('serializer', pickle)
        return super(PickleSerializerMixin, self).make_serializer(*args, **kwargs)


class URLSafeSerializerTestCase(URLSafeSerializerMixin, SerializerTestCase):
    serializer_class = idmod.URLSafeSerializer


class URLSafeTimedSerializerTestCase(URLSafeSerializerMixin, TimedSerializerTestCase):
    serializer_class = idmod.URLSafeTimedSerializer


class PickleSerializerTestCase(PickleSerializerMixin, SerializerTestCase):
    pass


class PickleTimedSerializerTestCase(PickleSerializerMixin, TimedSerializerTestCase):
    pass


class PickleURLSafeSerializerTestCase(PickleSerializerMixin, URLSafeSerializerTestCase):
    pass


class PickleURLSafeTimedSerializerTestCase(PickleSerializerMixin, URLSafeTimedSerializerTestCase):
    pass


if __name__ == '__main__':
    unittest.main()
