import unittest

import pulsar


class Context(object):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self._result = value
        return True


class TestApi(unittest.TestCase):

    def test_with_statement(self):
        with Context() as c:
            yield None
            yield None
            raise ValueError
        self.assertIsInstance(c._result, ValueError)

    def test_get_proxy(self):
        self.assertRaises(ValueError, pulsar.get_proxy, 'shcbjsbcjcdcd')
        self.assertEqual(pulsar.get_proxy('shcbjsbcjcdcd', safe=True), None)

    def test_bad_concurrency(self):
        # bla concurrency does not exists
        actor = yield pulsar.spawn(kind='bla')
        self.assertFalse(actor)

    def test_actor_coverage(self):
        '''test case for coverage'''
        return self.async.assertRaises(pulsar.CommandNotFound,
                                       pulsar.send, 'arbiter',
                                       'sjdcbhjscbhjdbjsj', 'bla')
