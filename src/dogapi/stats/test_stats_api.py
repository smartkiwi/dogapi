"""
Tests for the DogStatsAPI class.
"""


import time

import nose.tools as nt

from dogapi import DogStatsApi


#
# Test fixtures.
#

class MemoryReporter(object):
    """ A reporting class that reports to memory for testing. """

    def __init__(self):
        self.metrics = []

    def flush(self, metrics):
        self.metrics += metrics


#
# Test code.
#

class TestDogStatsAPI(object):

    def sort_metrics(self, metrics):
        """ Sort metrics by timestamp of first point and then name """
        sort = lambda metric: (metric['points'][0][0], metric['metric'])
        return sorted(metrics, key=sort)

    def test_timed_decorator(self):
        dog = DogStatsApi(roll_up_interval=1, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()

        @dog.timed('timed.test')
        def func(a, b, c=1, d=1):
            return (a, b, c, d)

        result = func(1, 2, d=3)
        # Assert it handles args and kwargs correctly.
        nt.assert_equal(result, (1, 2, 1, 3))
        time.sleep(1) # Argh. I hate this.
        dog.flush()
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 2)
        (avg, count) = metrics
        nt.assert_equal(avg['metric'], 'timed.test.avg')
        nt.assert_equal(count['metric'], 'timed.test.count')

    def test_histogram(self):
        dog = DogStatsApi(roll_up_interval=10, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()

        # Add some histogram metrics.
        dog.histogram('histogram.1', 20, 100.0)
        dog.histogram('histogram.1', 25, 105.0)
        dog.histogram('histogram.1', 30, 106.0)

        dog.histogram('histogram.1', 30, 110.0)
        dog.histogram('histogram.1', 50, 115.0)
        dog.histogram('histogram.1', 40, 116.0)

        dog.histogram('histogram.2', 40, 100.0)

        dog.histogram('histogram.3', 50, 134.0)

        # Flush and ensure they roll up properly.
        dog.flush(120.0)
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 6)

        (h1avg1, h1cnt1, h2avg1, h2cnt1, h1avg2, h1cnt2) = metrics

        nt.assert_equal(h1avg1['metric'], 'histogram.1.avg')
        nt.assert_equal(h1avg1['points'][0][0], 100.0)
        nt.assert_equal(h1avg1['points'][0][1], 25)
        nt.assert_equal(h1cnt1['metric'], 'histogram.1.count')
        nt.assert_equal(h1cnt1['points'][0][0], 100.0)
        nt.assert_equal(h1cnt1['points'][0][1], 3)

        nt.assert_equal(h1avg2['metric'], 'histogram.1.avg')
        nt.assert_equal(h1avg2['points'][0][0], 110.0)
        nt.assert_equal(h1avg2['points'][0][1], 40)
        nt.assert_equal(h1cnt2['metric'], 'histogram.1.count')
        nt.assert_equal(h1cnt2['points'][0][0], 110.0)
        nt.assert_equal(h1cnt2['points'][0][1], 3)

        nt.assert_equal(h2avg1['metric'], 'histogram.2.avg')
        nt.assert_equal(h2avg1['points'][0][0], 100.0)
        nt.assert_equal(h2avg1['points'][0][1], 40)
        nt.assert_equal(h2cnt1['metric'], 'histogram.2.count')
        nt.assert_equal(h2cnt1['points'][0][0], 100.0)
        nt.assert_equal(h2cnt1['points'][0][1], 1)

        # Flush agin ensure they're gone.
        dog.reporter.metrics = []
        dog.flush(140.0)
        nt.assert_equal(len(dog.reporter.metrics), 2)
        dog.reporter.metrics = []
        dog.flush(200.0)
        nt.assert_equal(len(dog.reporter.metrics), 0)

    def test_gauge(self):

        # Create some fake metrics.
        dog = DogStatsApi(roll_up_interval=10, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()

        dog.gauge('test.gauge.1', 20, 100.0)
        dog.gauge('test.gauge.1', 22, 105.0)
        dog.gauge('test.gauge.2', 30, 115.0)
        dog.gauge('test.gauge.3', 30, 125.0)
        dog.flush(120.0)

        # Assert they've been properly flushed.
        metrics = reporter.metrics
        nt.assert_equal(len(metrics), 2)

        (first, second) = metrics
        nt.assert_equal(first['metric'], 'test.gauge.1')
        nt.assert_equal(first['points'][0][0], 100.0)
        nt.assert_equal(first['points'][0][1], 22)
        nt.assert_equal(second['metric'], 'test.gauge.2')

        # Flush again and make sure we're progressing.
        reporter.metrics = []
        dog.flush(130.0)
        nt.assert_equal(len(reporter.metrics), 1)

        # Finally, make sure we've flushed all metrics.
        reporter.metrics = []
        dog.flush(150.0)
        nt.assert_equal(len(reporter.metrics), 0)

    def test_counter(self):
        # Create some fake metrics.
        dog = DogStatsApi(roll_up_interval=10, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()

        dog.increment('test.counter.1', timestamp=1000.0)
        dog.increment('test.counter.1', value=2, timestamp=1005.0)
        dog.increment('test.counter.2', timestamp=1015.0)
        dog.increment('test.counter.3', timestamp=1025.0)
        dog.flush(1021.0)

        # Assert they've been properly flushed.
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 2)
        (first, second) = metrics
        nt.assert_equal(first['metric'], 'test.counter.1')
        nt.assert_equal(first['points'][0][0], 1000.0)
        nt.assert_equal(first['points'][0][1], 3)
        nt.assert_equal(second['metric'], 'test.counter.2')

        # Flush again and make sure we're progressing.
        reporter.metrics = []
        dog.flush(1030.0)
        nt.assert_equal(len(reporter.metrics), 1)

        # Finally, make sure we've flushed all metrics.
        reporter.metrics = []
        dog.flush(1050.0)
        nt.assert_equal(len(reporter.metrics), 0)


    def test_max_flush_size(self):
        dog = DogStatsApi(flush_in_thread=False, flush_interval=10, max_flush_size=10)
        reporter = dog.reporter = MemoryReporter()
        for i in range(100):
            dog.gauge('flush.size.%s' % i, i, 123.435)
        dog.flush(1000.0)
        nt.assert_equal(len(reporter.metrics), 10)
        dog.flush(1100.0)
        nt.assert_equal(len(reporter.metrics), 20)

    def test_max_queue_size(self):
        dog = DogStatsApi(max_queue_size=5, roll_up_interval=1, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()
        for i in range(10):
            dog.gauge('my.gauge.%s' % i,  1, 1000.0)
        dog.flush(2000.0)
        nt.assert_equal(len(reporter.metrics), 5)

    def test_default_host_and_device(self):
        dog = DogStatsApi(roll_up_interval=1, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('my.gauge', 1, 100.0)
        dog.flush(1000)
        metric = reporter.metrics[0]
        assert not metric['device']
        assert metric['host']

    def test_custom_host_and_device(self):
        dog = DogStatsApi(roll_up_interval=1, flush_in_thread=False, host='host', device='dev')
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('my.gauge', 1, 100.0)
        dog.flush(1000)
        metric = reporter.metrics[0]
        nt.assert_equal(metric['device'], 'dev')
        nt.assert_equal(metric['host'], 'host')





