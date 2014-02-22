import sys
import unittest
import logging
from unittest.case import _ExpectedFailure as ExpectedFailure

from pulsar import multi_async, coroutine_return
from pulsar.utils.pep import ispy3k
from pulsar.apps import tasks

from .utils import TestFunction

if ispy3k:
    from unittest import mock
else:  # pragma nocover
    try:
        import mock
    except ImportError:
        mock = None


LOGGER = logging.getLogger('pulsar.test')


class Test(tasks.Job):
    '''A :class:`.Job` for running tests on a task queue.
    '''
    def __call__(self, consumer, testcls=None, tag=None):
        runner = consumer.worker.app.new_runner()
        if not isinstance(testcls, type):
            testcls = testcls()
        testcls.tag = tag
        testcls.cfg = consumer.worker.cfg
        all_tests = runner.loadTestsFromTestCase(testcls)
        num = all_tests.countTestCases()
        if num:
            return self.run(runner, testcls, all_tests, consumer.worker.cfg)
        else:
            return runner.result

    def create_id(self, kwargs):
        tid = super(Test, self).create_id(kwargs)
        testcls = kwargs.get('testcls')
        return '%s_%s' % (testcls.__name__, tid) if testcls else tid

    def run(self, runner, testcls, all_tests, cfg):
        '''Run all test functions from the :attr:`testcls`.

        It uses the following algorithm:

        * Run the class method ``setUpClass`` of :attr:`testcls` if defined,
          unless the test class should be skipped
        * Call :meth:`run_test` for each test functions in :attr:`testcls`
        * Run the class method ``tearDownClass`` of :attr:`testcls` if defined,
          unless the test class should be skipped.
        '''
        runner.startTestClass(testcls)
        error = None
        timeout = cfg.test_timeout
        sequential = getattr(testcls, '_sequential_execution', cfg.sequential)
        skip_tests = getattr(testcls, '__unittest_skip__', False)
        if not skip_tests:
            error = yield self._run(runner, testcls, 'setUpClass', timeout,
                                    add_err=False)
        # run the tests
        if not error:
            if sequential:
                # Loop over all test cases in class
                for test in all_tests:
                    yield self.run_test(test, runner, cfg)
            else:
                all = (self.run_test(test, runner, cfg) for test in all_tests)
                yield multi_async(all)
        else:
            for test in all_tests:
                runner.startTest(test)
                self.add_failure(test, runner, error[0], error[1])
                runner.stopTest(test)
        if not skip_tests:
            yield self._run(runner, testcls, 'tearDownClass', timeout,
                            add_err=False)
        runner.stopTestClass(testcls)
        coroutine_return(runner.result)

    def run_test(self, test, runner, cfg):
        '''Run a ``test`` function using the following algorithm

        * Run :meth:`_pre_setup` method if available in :attr:`testcls`.
        * Run :meth:`setUp` method in :attr:`testcls`.
        * Run the test function.
        * Run :meth:`tearDown` method in :attr:`testcls`.
        * Run :meth:`_post_teardown` method if available in :attr:`testcls`.
        '''
        timeout = cfg.test_timeout
        err = None
        try:
            runner.startTest(test)
            testMethod = getattr(test, test._testMethodName)
            if (getattr(test.__class__, '__unittest_skip__', False) or
                    getattr(testMethod, '__unittest_skip__', False)):
                reason = (getattr(test.__class__,
                                  '__unittest_skip_why__', '') or
                          getattr(testMethod,
                                  '__unittest_skip_why__', ''))
                runner.addSkip(test, reason)
                err = True
            else:
                err = yield self._run(runner, test, '_pre_setup', timeout)
                if not err:
                    err = yield self._run(runner, test, 'setUp', timeout)
                    if not err:
                        err = yield self._run(runner, test,
                                              test._testMethodName, timeout)
                    err = yield self._run(runner, test, 'tearDown',
                                          timeout, err)
                err = yield self._run(runner, test, '_post_teardown',
                                      timeout, err)
                runner.stopTest(test)
        except Exception as error:
            self.add_failure(test, runner, error, err)
        else:
            if not err:
                runner.addSuccess(test)

    def _run(self, runner, test, method, timeout, previous=None, add_err=True):
        __skip_traceback__ = True
        method = getattr(test, method, None)
        if method:
            # Check if a testfunction object is already available
            # Check the run_on_arbiter decorator for information
            tfunc = getattr(method, 'testfunction', None)
            if tfunc is None:
                tfunc = TestFunction(method.__name__)
            try:
                exc = yield tfunc(test, timeout)
            except Exception as e:
                exc = e
            if exc:
                add_err = False if previous else add_err
                previous = self.add_failure(test, runner, exc, add_err)
        coroutine_return(previous)

    def add_failure(self, test, runner, error, add_err=True):
        '''Add ``error`` to the list of errors.

        :param test: the test function object where the error occurs
        :param runner: the test runner
        :param error: the python exception for the error
        :param add_err: if ``True`` the error is added to the list of errors
        :return: a tuple containing the ``error`` and the ``exc_info``
        '''
        if add_err:
            if isinstance(error, test.failureException):
                runner.addFailure(test, error)
            elif isinstance(error, ExpectedFailure):
                runner.addExpectedFailure(test, error)
            else:
                runner.addError(test, error)
        else:
            LOGGER.exception('exception')
        return error
