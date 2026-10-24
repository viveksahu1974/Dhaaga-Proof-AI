import sys
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from engine import allocate,quote,gini,agent_plan


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.order={'id':5,'due_date':(date.today()+timedelta(days=5)).isoformat(),
                    'quantity':60,'category':'garments','material_per_unit':40,
                    'labour_rate_hour':60,'minutes_per_unit':30,
                    'overhead_per_unit':10,'target_margin_pct':20,
                    'buyer_price_per_unit':125,'product':'bags','status':'draft'}
        self.members=[{'id':i,'name':f'Worker {i}','skill':'garments',
                       'capacity_per_day':5,'consent':1,'jobs_done':4,'jobs_late':1}
                      for i in range(1,4)]

    def test_quote_margin_and_unit_labour(self):
        q=quote(self.order)
        self.assertEqual(q['labour'],30)
        self.assertEqual(q['unit_cost'],80)
        self.assertEqual(q['min_quote_for_target'],100)
        self.assertAlmostEqual(q['margin_pct'],36)

    def test_capacity_consent_and_allocation_sum(self):
        p=allocate(self.order,self.members)
        self.assertEqual(p['allocated_units'],60)
        self.assertEqual(p['unallocated_units'],0)
        self.assertEqual(sum(a['allocated'] for a in p['allocations']),60)
        self.members[0]['consent']=0
        remaining=allocate(self.order,self.members)
        self.assertTrue(all(a['id']!=1 for a in remaining['allocations']))
        self.assertEqual(remaining['allocated_units'],60)

    def test_no_consented_capacity(self):
        for m in self.members:m['consent']=0
        p=allocate(self.order,self.members)
        self.assertEqual(p['unallocated_units'],60)
        self.assertEqual(p['allocations'],[])

    def test_explainability_and_gini(self):
        p=allocate(self.order,self.members)
        self.assertEqual(gini([1,1,1]),0)
        self.assertTrue(all('capacity' in a['reason'] for a in p['allocations']))
        self.assertTrue(p['human_approval_required'])

    def test_agent_never_executes_actions(self):
        a=agent_plan(self.order,[],self.members)
        self.assertIn('No external action',a['execution'])
        self.assertTrue(all(x['human_approval'] for x in a['proposed_actions']))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_db=app.DB_PATH
        app.DB_PATH=Path(self.temp.name)/'test.sqlite3'
        app.init_db()

    def tearDown(self):
        app.DB_PATH=self.old_db
        self.temp.cleanup()

    def test_seed_is_fictional_and_audit_verifies(self):
        s=app.state()
        self.assertTrue(s['demo_mode'])
        self.assertTrue(s['audit_valid'])
        self.assertEqual(len(s['orders']),2)
        self.assertEqual(len(s['members']),8)

    def test_plan_requires_approval_and_cannot_be_duplicated(self):
        p=app.preview_plan(2)
        self.assertEqual(p['allocated_units'],150)
        self.assertEqual(p['unallocated_units'],0)
        app.approve_plan(2)
        with self.assertRaises(ValueError):app.approve_plan(2)
        s=app.state()
        self.assertTrue(s['audit_valid'])
        self.assertEqual(next(o for o in s['orders'] if o['id']==2)['assigned_units'],150)

    def test_accepted_units_only_generate_wages(self):
        state=app.state()
        assignment=next(o for o in state['orders'] if o['id']==1)['assignments'][0]
        remaining=assignment['allocated_units']-assignment['completed_units']
        self.assertGreaterEqual(remaining,3)
        app.update_progress({'assignment_id':assignment['id'],'produced_increment':3,'accepted_increment':1})
        p=app.settlement_preview(1)
        entry=next(x for x in p['members'] if x['assignment_id']==assignment['id'])
        expected=(assignment['accepted_units']+1)*assignment['labour_rate_hour']*assignment['minutes_per_unit']/60
        self.assertAlmostEqual(entry['earned'],expected)
        self.assertGreater(p['total_new_due'],0)
        result=app.approve_settlement(1)
        self.assertIn('No money transferred',result['message'])
        self.assertEqual(app.settlement_preview(1)['total_new_due'],0)
        self.assertTrue(app.state()['audit_valid'])

    def test_overproduction_rejected(self):
        assignment=next(o for o in app.state()['orders'] if o['id']==1)['assignments'][0]
        with self.assertRaises(ValueError):
            app.update_progress({'assignment_id':assignment['id'],'produced_increment':10000,'accepted_increment':10000})

    def test_audit_tampering_detected(self):
        with app.connect() as c:
            c.execute("UPDATE audit SET payload='{}' WHERE id=1")
        self.assertFalse(app.state()['audit_valid'])

    def test_consent_excludes_new_plans(self):
        app.set_consent(1,False)
        p=app.preview_plan(2)
        self.assertFalse(any(m['id']==1 for m in p['allocations']))


if __name__=='__main__':unittest.main(verbosity=2)

class EndToEndScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_db=app.DB_PATH
        app.DB_PATH=Path(self.temp.name)/'scenario.sqlite3'
        app.init_db()

    def tearDown(self):
        app.DB_PATH=self.old_db
        self.temp.cleanup()

    def test_create_plan_approve_progress_pay(self):
        created=app.make_order({
            'buyer':'Example buyer','product':'Handmade pouches','category':'garments',
            'quantity':35,'buyer_price_per_unit':190,'material_per_unit':60,
            'labour_rate_hour':90,'minutes_per_unit':30,'overhead_per_unit':12,
            'target_margin_pct':20,'due_date':(date.today()+timedelta(days=8)).isoformat()})
        oid=created['order_id']
        self.assertGreater(oid,2)
        before=next(o for o in app.state()['orders'] if o['id']==oid)
        self.assertEqual(before['status'],'draft')
        self.assertFalse(before['assignments'])
        plan=app.preview_plan(oid)
        self.assertEqual(plan['allocated_units'],35)
        app.approve_plan(oid)
        after=next(o for o in app.state()['orders'] if o['id']==oid)
        self.assertEqual(after['assigned_units'],35)
        worker=after['assignments'][0]
        app.update_progress({'assignment_id':worker['id'],'produced_increment':2,'accepted_increment':1})
        payout=app.settlement_preview(oid)
        self.assertEqual(payout['total_new_due'],45)
        self.assertEqual(app.approve_settlement(oid)['preview']['total_new_due'],45)
        final=app.state()
        self.assertTrue(final['audit_valid'])
        self.assertEqual(app.settlement_preview(oid)['total_new_due'],0)

    def test_rejection_not_paid(self):
        a=next(o for o in app.state()['orders'] if o['id']==1)['assignments'][0]
        old=app.settlement_preview(1)['total_new_due']
        app.update_progress({'assignment_id':a['id'],'produced_increment':2,'accepted_increment':0})
        self.assertEqual(old,app.settlement_preview(1)['total_new_due'])


class AgentActionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_db=app.DB_PATH
        app.DB_PATH=Path(self.temp.name)/'action.sqlite3'
        app.init_db()

    def tearDown(self):
        app.DB_PATH=self.old_db
        self.temp.cleanup()

    def test_agent_creates_approval_gated_persistent_work(self):
        output=app.run_agent(1)
        self.assertGreaterEqual(len(output['action_ids']),1)
        action_id=output['action_ids'][0]
        self.assertEqual(next(a for a in app.state()['agent_actions'] if a['id']==action_id)['status'],'proposed')
        prepared=app.approve_agent_action(action_id)
        self.assertIn('UNSENT',prepared['message'])
        s=app.state()
        self.assertGreater(len(s['message_drafts']),0)
        self.assertTrue(all(d['status']=='UNSENT DEMO' for d in s['message_drafts']))
        self.assertTrue(s['audit_valid'])
        with self.assertRaises(ValueError): app.approve_agent_action(action_id)

    def test_agent_proposal_deduplicates_pending(self):
        first=app.run_agent(2)
        second=app.run_agent(2)
        self.assertEqual(first['action_ids'],second['action_ids'])
