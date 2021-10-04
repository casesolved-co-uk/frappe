from unittest import TestCase
from dateutil.relativedelta import relativedelta
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
from frappe.utils.background_jobs import enqueue, get_jobs
from frappe.utils.scheduler import enqueue_events, is_dormant, schedule_jobs_based_on_activity
from frappe.utils import add_days, get_datetime
from frappe.utils.doctor import purge_pending_jobs

import frappe
import time

def test_timeout():
	time.sleep(100)

def test_timeout_10():
	time.sleep(10)

def test_method():
	pass
class TestScheduler(TestCase):
	def setUp(self):
		purge_pending_jobs()
		if not frappe.get_all('Scheduled Job Type', limit=1):
			sync_jobs()

	def test_enqueue_jobs(self):
		frappe.db.sql("update `tabScheduled Job Type` set last_execution = '2010-01-01 00:00:00'")

		frappe.flags.execute_job = True
		enqueue_events(site = frappe.local.site)
		frappe.flags.execute_job = False

		self.assertTrue('frappe.email.queue.set_expiry_for_email_queue', frappe.flags.enqueued_jobs)
		self.assertTrue('frappe.utils.change_log.check_for_update', frappe.flags.enqueued_jobs)
		self.assertTrue('frappe.email.doctype.auto_email_report.auto_email_report.send_monthly', frappe.flags.enqueued_jobs)

	def test_queue_peeking(self):
		job = get_test_job()

		self.assertTrue(job.enqueue())
		job.db_set('last_execution', '2010-01-01 00:00:00')
		frappe.db.commit()

		time.sleep(0.5)

		# 1st job is in the queue (or running), don't enqueue it again
		self.assertFalse(job.enqueue())
		frappe.db.delete("Scheduled Job Log", {"scheduled_job_type": job.name})

	def test_is_dormant(self):
		self.assertTrue(is_dormant(check_time= get_datetime('2100-01-01 00:00:00')))
		self.assertTrue(is_dormant(check_time = add_days(frappe.db.get_last_created('Activity Log'), 5)))
		self.assertFalse(is_dormant(check_time = frappe.db.get_last_created('Activity Log')))

	def test_once_a_day_for_dormant(self):
		frappe.db.clear_table('Scheduled Job Log')
		self.assertTrue(schedule_jobs_based_on_activity(check_time= get_datetime('2100-01-01 00:00:00')))
		self.assertTrue(schedule_jobs_based_on_activity(check_time = add_days(frappe.db.get_last_created('Activity Log'), 5)))

		# create a fake job executed 5 days from now
		job = get_test_job(method='frappe.tests.test_scheduler.test_method', frequency='Daily')
		job.execute()
		job_log = frappe.get_doc('Scheduled Job Log', dict(scheduled_job_type=job.name))
		job_log.db_set('creation', add_days(frappe.db.get_last_created('Activity Log'), 5))

		# inactive site with recent job, don't run
		self.assertFalse(schedule_jobs_based_on_activity(check_time = add_days(frappe.db.get_last_created('Activity Log'), 5)))

		# one more day has passed
		self.assertTrue(schedule_jobs_based_on_activity(check_time = add_days(frappe.db.get_last_created('Activity Log'), 6)))

		frappe.db.rollback()

	def test_job_timeout(self):
		return
		job = enqueue(test_timeout, timeout=10)
		count = 5
		while count > 0:
			count -= 1
			time.sleep(5)
			if job.get_status()=='failed':
				break

		self.assertTrue(job.is_failed)

def get_test_job(method='frappe.tests.test_scheduler.test_timeout_10', frequency='All'):
	if not frappe.db.exists('Scheduled Job Type', dict(method=method)):
		job = frappe.get_doc(dict(
			doctype = 'Scheduled Job Type',
			method = method,
			last_execution = '2010-01-01 00:00:00',
			frequency = frequency
		)).insert()
	else:
		job = frappe.get_doc('Scheduled Job Type', dict(method=method))
		job.db_set('last_execution', '2010-01-01 00:00:00')
		job.db_set('frequency', frequency)
	frappe.db.commit()

	return job

