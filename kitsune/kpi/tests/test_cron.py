from datetime import date

from mock import patch
from nose.tools import eq_

import kitsune.kpi.cron
from kitsune.kpi.cron import (
    update_visitors_metric, update_l10n_metric, googleanalytics,
    update_search_ctr_metric)
from kitsune.kpi.models import (Metric, VISITORS_METRIC_CODE,
                                L10N_METRIC_CODE, SEARCH_CLICKS_METRIC_CODE,
                                SEARCH_SEARCHES_METRIC_CODE)
from kitsune.kpi.tests import metric_kind
from kitsune.sumo.tests import TestCase
from kitsune.wiki.config import (
    MAJOR_SIGNIFICANCE, MEDIUM_SIGNIFICANCE, TYPO_SIGNIFICANCE)
from kitsune.wiki.tests import document, revision


class CronJobTests(TestCase):
    @patch.object(googleanalytics, 'visitors')
    def test_update_visitors_cron(self, visitors):
        """Verify the cron job inserts the right rows."""
        visitor_kind = metric_kind(code=VISITORS_METRIC_CODE, save=True)
        visitors.return_value = {'2012-01-13': 42,
                               '2012-01-14': 193,
                               '2012-01-15': 33}

        update_visitors_metric()

        metrics = Metric.objects.filter(kind=visitor_kind).order_by('start')
        eq_(3, len(metrics))
        eq_(42, metrics[0].value)
        eq_(193, metrics[1].value)
        eq_(date(2012, 01, 15), metrics[2].start)

    @patch.object(kitsune.kpi.cron, '_get_top_docs')
    @patch.object(googleanalytics, 'visitors_by_locale')
    def test_update_l10n_metric_cron(self, visitors_by_locale, _get_top_docs):
        """Verify the cron job creates the correct metric."""
        l10n_kind = metric_kind(code=L10N_METRIC_CODE, save=True)

        # Create the en-US document with an approved revision.
        doc = document(save=True)
        rev = revision(
            document=doc,
            significance=MEDIUM_SIGNIFICANCE,
            is_approved=True,
            is_ready_for_localization=True,
            save=True)

        # Create an es translation that is up to date.
        es_doc = document(parent=doc, locale='es', save=True)
        revision(
            document=es_doc,
            is_approved=True,
            based_on=rev,
            save=True)

        # Create a de translation without revisions.
        document(parent=doc, locale='de', save=True)

        # Mock some calls.
        visitors_by_locale.return_value = {
            'en-US': 50,
            'de': 20,
            'es': 25,
            'fr': 5,
        }
        _get_top_docs.return_value = [doc]

        # Run it and verify results.
        # Value should be 75% (1/1 * 25/100 + 1/1 * 50/100)
        update_l10n_metric()
        metrics = Metric.objects.filter(kind=l10n_kind)
        eq_(1, len(metrics))
        eq_(75, metrics[0].value)

        # Create a new revision with TYPO_SIGNIFICANCE. It shouldn't
        # affect the results.
        revision(
            document=doc,
            significance=TYPO_SIGNIFICANCE,
            is_approved=True,
            is_ready_for_localization=True,
            save=True)
        Metric.objects.all().delete()
        update_l10n_metric()
        metrics = Metric.objects.filter(kind=l10n_kind)
        eq_(1, len(metrics))
        eq_(75, metrics[0].value)

        # Create a new revision with MEDIUM_SIGNIFICANCE. The coverage
        # should now be 62% (0.5/1 * 25/100 + 1/1 * 50/100)
        m1 = revision(
            document=doc,
            significance=MEDIUM_SIGNIFICANCE,
            is_approved=True,
            is_ready_for_localization=True,
            save=True)
        Metric.objects.all().delete()
        update_l10n_metric()
        metrics = Metric.objects.filter(kind=l10n_kind)
        eq_(1, len(metrics))
        eq_(62, metrics[0].value)

        # And another new revision with MEDIUM_SIGNIFICANCE makes the
        # coverage 50% (1/1 * 50/100).
        m2 = revision(
            document=doc,
            significance=MEDIUM_SIGNIFICANCE,
            is_approved=True,
            is_ready_for_localization=True,
            save=True)
        Metric.objects.all().delete()
        update_l10n_metric()
        metrics = Metric.objects.filter(kind=l10n_kind)
        eq_(1, len(metrics))
        eq_(50, metrics[0].value)

        # If we remove the two MEDIUM_SIGNIFICANCE revisions and add a
        # MAJOR_SIGNIFICANCE revision, the coverage is 50% as well.
        m1.delete()
        m2.delete()
        revision(
            document=doc,
            significance=MAJOR_SIGNIFICANCE,
            is_approved=True,
            is_ready_for_localization=True,
            save=True)
        Metric.objects.all().delete()
        update_l10n_metric()
        metrics = Metric.objects.filter(kind=l10n_kind)
        eq_(1, len(metrics))
        eq_(50, metrics[0].value)

    @patch.object(googleanalytics, 'search_ctr')
    def test_update_search_ctr(self, search_ctr):
        """Verify the cron job inserts the right rows."""
        clicks_kind = metric_kind(code=SEARCH_CLICKS_METRIC_CODE, save=True)
        metric_kind(code=SEARCH_SEARCHES_METRIC_CODE, save=True)
        search_ctr.return_value = {'2013-06-06': 42.123456789,
                                   '2013-06-07': 13.7654321,
                                   '2013-06-08': 99.55555}

        update_search_ctr_metric()

        metrics = Metric.objects.filter(kind=clicks_kind).order_by('start')
        eq_(3, len(metrics))
        eq_(421, metrics[0].value)
        eq_(138, metrics[1].value)
        eq_(date(2013, 6, 8), metrics[2].start)
