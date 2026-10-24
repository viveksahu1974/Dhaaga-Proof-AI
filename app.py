"""DhaagaProof AI: local-first prototype, using Python 3.11+ standard library only.

Start: python app.py
Open:  http://127.0.0.1:8765
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import threading
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse, parse_qs
from engine import allocate, quote, signals, agent_plan, money

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
DB_PATH = Path(os.getenv('DHAAGAPROOF_DB', str(ROOT / 'dhaagaproof.sqlite3')))
HOST = os.getenv('DHAAGAPROOF_HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', 8765))
LOCK = threading.RLock()


@contextmanager
def connect():
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(c, sql, args=()):
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None


def record(c, kind, payload):
    previous = one(c, 'SELECT digest FROM audit ORDER BY id DESC LIMIT 1')
    prev = previous['digest'] if previous else 'GENESIS'
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = sha256((prev + '|' + kind + '|' + content).encode('utf-8')).hexdigest()
    c.execute('INSERT INTO audit (kind,payload,previous_hash,digest) VALUES (?,?,?,?)',
              (kind, content, prev, digest))


def verify_audit(c):
    prev = 'GENESIS'
    for r in rows(c, 'SELECT * FROM audit ORDER BY id'):
        check = sha256((prev + '|' + r['kind'] + '|' + r['payload']).encode('utf-8')).hexdigest()
        if check != r['digest'] or prev != r['previous_hash']:
            return False
        prev = r['digest']
    return True


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK, connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS members (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, skill TEXT NOT NULL,
          capacity_per_day INTEGER NOT NULL, consent INTEGER NOT NULL DEFAULT 1,
          jobs_done INTEGER NOT NULL DEFAULT 0, jobs_late INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS orders (
          id INTEGER PRIMARY KEY, buyer TEXT NOT NULL, product TEXT NOT NULL,
          category TEXT NOT NULL, quantity INTEGER NOT NULL,
          buyer_price_per_unit REAL NOT NULL, material_per_unit REAL NOT NULL,
          labour_rate_hour REAL NOT NULL, minutes_per_unit REAL NOT NULL,
          overhead_per_unit REAL NOT NULL, target_margin_pct REAL NOT NULL,
          due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft'
        );
        CREATE TABLE IF NOT EXISTS assignments (
          id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
          member_id INTEGER NOT NULL REFERENCES members(id),
          allocated_units INTEGER NOT NULL, completed_units INTEGER NOT NULL DEFAULT 0,
          accepted_units INTEGER NOT NULL DEFAULT 0, approved_payout REAL NOT NULL DEFAULT 0,
          UNIQUE(order_id,member_id)
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          kind TEXT NOT NULL, payload TEXT NOT NULL,
          previous_hash TEXT NOT NULL, digest TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_actions (
          id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
          action_type TEXT NOT NULL, title TEXT NOT NULL, reason TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'proposed', outcome TEXT NOT NULL DEFAULT '',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS message_drafts (
          id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
          member_id INTEGER NOT NULL REFERENCES members(id),
          text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'UNSENT DEMO',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        if one(c, 'SELECT COUNT(*) AS n FROM members')['n']:
            return
        people = [
            ('Kiran', 'garments', 9, 1, 16, 1), ('Meera', 'garments', 8, 1, 10, 1),
            ('Pooja', 'garments', 7, 1, 12, 3), ('Saira', 'garments', 10, 1, 18, 1),
            ('Anjali', 'mixed', 7, 1, 8, 1), ('Farida', 'garments', 8, 1, 9, 2),
            ('Ritu', 'food', 10, 1, 14, 2), ('Nusrat', 'mixed', 7, 1, 7, 0)
        ]
        c.executemany('INSERT INTO members (name,skill,capacity_per_day,consent,jobs_done,jobs_late) VALUES (?,?,?,?,?,?)', people)
        due1 = (date.today() + timedelta(days=5)).isoformat()
        due2 = (date.today() + timedelta(days=12)).isoformat()
        c.execute('''INSERT INTO orders (buyer,product,category,quantity,buyer_price_per_unit,
                material_per_unit,labour_rate_hour,minutes_per_unit,overhead_per_unit,
                target_margin_pct,due_date,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('Sahyog Stores', 'Handmade cotton tote bags', 'garments', 240, 165, 72, 72, 22, 8, 22, due1, 'active'))
        c.execute('''INSERT INTO orders (buyer,product,category,quantity,buyer_price_per_unit,
                material_per_unit,labour_rate_hour,minutes_per_unit,overhead_per_unit,
                target_margin_pct,due_date,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('LokMart Collective', 'Festival gift pouches', 'garments', 150, 118, 56, 72, 19, 7, 20, due2, 'draft'))
        allocations = [(1,1,45,28,26),(1,2,39,32,31),(1,3,35,20,17),
                       (1,4,50,44,43),(1,5,34,13,12),(1,6,37,19,18)]
        c.executemany('''INSERT INTO assignments (order_id,member_id,allocated_units,completed_units,accepted_units)
                         VALUES (?,?,?,?,?)''', allocations)
        record(c, 'demo_dataset_initialized', {'fictional_data': True, 'members': len(people), 'orders': 2})


def assignment_rows(c, order_id=None):
    where, params = ('WHERE a.order_id=?', (int(order_id),)) if order_id else ('', ())
    return rows(c, '''SELECT a.*, m.name AS member_name, m.capacity_per_day,
                       o.product, o.labour_rate_hour, o.minutes_per_unit
                    FROM assignments a JOIN members m ON m.id=a.member_id
                    JOIN orders o ON o.id=a.order_id ''' + where + ' ORDER BY a.id', params)


def workload_by_member(c, excluding_order=None):
    w = {}
    for r in rows(c, 'SELECT * FROM assignments'):
        if excluding_order is not None and r['order_id'] == excluding_order:
            continue
        w[r['member_id']] = w.get(r['member_id'], 0) + (r['allocated_units'] - r['completed_units'])
    return w


def enriched_order(c, o):
    a = assignment_rows(c, o['id'])
    for x in a:
        unitpay = x['labour_rate_hour'] * x['minutes_per_unit'] / 60
        x['earned'] = money(x['accepted_units'] * unitpay)
        x['due_payout'] = money(max(0, x['earned'] - x['approved_payout']))
    done = sum(x['completed_units'] for x in a)
    accepted = sum(x['accepted_units'] for x in a)
    o['completed_units'] = done
    o['accepted_units'] = accepted
    o['assigned_units'] = sum(x['allocated_units'] for x in a)
    o['progress_pct'] = round(100 * done / o['quantity'], 1)
    o['quote'] = quote(o)
    o['alerts'] = signals(o, a)
    o['assignments'] = a
    o['earnings_total'] = money(sum(x['earned'] for x in a))
    o['payouts_approved'] = money(sum(x['approved_payout'] for x in a))
    return o


def state():
    with connect() as c:
        members = rows(c, 'SELECT * FROM members ORDER BY id')
        orders = [enriched_order(c, o) for o in rows(c, 'SELECT * FROM orders ORDER BY id DESC')]
        audit = rows(c, 'SELECT id,created_at,kind,payload,digest FROM audit ORDER BY id DESC LIMIT 20')
        return {
            'demo_mode': True, 'security_notice': 'Local demo: not multi-user production-ready. Fictional member names, orders and figures.',
            'members': members, 'orders': orders,
            'audit': audit, 'audit_valid': verify_audit(c),
            'agent_actions': rows(c,'SELECT * FROM agent_actions ORDER BY id DESC LIMIT 30'),
            'message_drafts': rows(c, '''SELECT d.*, m.name AS member_name FROM message_drafts d
                   JOIN members m ON m.id=d.member_id ORDER BY d.id DESC LIMIT 25'''),
            'metrics': {
                'active_orders': sum(o['status']=='active' for o in orders),
                'open_units': sum(max(0,o['quantity']-o['completed_units']) for o in orders),
                'approved_wages': money(sum(o['payouts_approved'] for o in orders)),
                'order_value': money(sum(o['quote']['total_order_value'] for o in orders)),
                'alerts': sum(a['level'] in ('warning','critical') for o in orders for a in o['alerts']),
            },
        }


def require_order(c, order_id):
    o = one(c, 'SELECT * FROM orders WHERE id=?', (int(order_id),))
    if not o:
        raise ValueError('Order not found')
    return o


def make_order(data):
    product = str(data.get('product', '')).strip()[:140]
    buyer = str(data.get('buyer', '')).strip()[:100]
    cat = str(data.get('category', 'garments'))
    if not product or not buyer or cat not in ('garments','food','craft'):
        raise ValueError('Enter buyer, product and a valid category')
    qty = int(data.get('quantity',0))
    if not 1 <= qty <= 5000:
        raise ValueError('Quantity must be 1 to 5000')
    fields = ['buyer_price_per_unit','material_per_unit','labour_rate_hour',
              'minutes_per_unit','overhead_per_unit','target_margin_pct']
    nums = [float(data.get(k,0)) for k in fields]
    if any(not (0 <= v <= 100000) for v in nums) or not (0 < nums[3] <= 1440) or not (0 <= nums[5] < 90):
        raise ValueError('Check costs, production time and margin target')
    due = date.fromisoformat(str(data.get('due_date','')))
    if due < date.today():
        raise ValueError('Due date cannot be in the past')
    with LOCK, connect() as c:
        cur = c.execute('''INSERT INTO orders (buyer,product,category,quantity,buyer_price_per_unit,
           material_per_unit,labour_rate_hour,minutes_per_unit,overhead_per_unit,target_margin_pct,due_date)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (buyer,product,cat,qty,*nums,due.isoformat()))
        ident = cur.lastrowid
        record(c,'order_created',{'order_id':ident,'product':product,'quantity':qty,'simulation':True})
    return {'order_id':ident}


def preview_plan(order_id):
    with connect() as c:
        o = require_order(c, order_id)
        if o['status'] != 'draft':
            raise ValueError('Order already approved; allocations cannot be overwritten')
        members = rows(c, 'SELECT * FROM members')
        return allocate(o,members,workload_by_member(c))


def approve_plan(order_id):
    with LOCK, connect() as c:
        o = require_order(c,order_id)
        if o['status'] != 'draft':
            raise ValueError('This plan is already approved')
        plan = allocate(o,rows(c,'SELECT * FROM members'),workload_by_member(c))
        if plan['unallocated_units']:
            raise ValueError('Not enough consenting capacity; reduce order quantity or extend due date')
        for m in plan['allocations']:
            c.execute('INSERT INTO assignments (order_id,member_id,allocated_units) VALUES (?,?,?)',
                      (order_id, m['id'], m['allocated']))
        c.execute("UPDATE orders SET status='active' WHERE id=?",(order_id,))
        record(c,'allocation_human_approved',{'order_id':order_id,'allocation':[[m['id'],m['allocated']] for m in plan['allocations']]})
        return {'message':'Assignments approved by demo SHG coordinator','plan':plan}


def update_progress(data):
    aid = int(data.get('assignment_id',0))
    produced = int(data.get('produced_increment',0))
    accepted = int(data.get('accepted_increment',0))
    if not 0 <= accepted <= produced <= 10000 or produced == 0:
        raise ValueError('Accepted units must be between 0 and newly produced units')
    with LOCK, connect() as c:
        a = one(c,'SELECT * FROM assignments WHERE id=?',(aid,))
        if not a:
            raise ValueError('Assignment not found')
        if a['completed_units'] + produced > a['allocated_units']:
            raise ValueError('Progress exceeds approved assigned units')
        c.execute('''UPDATE assignments SET completed_units=completed_units+?,
                     accepted_units=accepted_units+? WHERE id=?''',(produced,accepted,aid))
        record(c,'progress_recorded',{'assignment_id':aid,'produced':produced,'accepted':accepted})
        return {'message':'Progress and quality recorded','assignment_id':aid}


def settlement_preview(order_id):
    with connect() as c:
        require_order(c, order_id)
        payments=[]
        for a in assignment_rows(c,order_id):
            earned = money(a['accepted_units'] * a['labour_rate_hour'] * a['minutes_per_unit']/60)
            due = money(max(0,earned - a['approved_payout']))
            payments.append({'assignment_id':a['id'],'member':a['member_name'],
                            'accepted_units':a['accepted_units'],'earned':earned,
                            'already_approved':a['approved_payout'],'new_due':due})
        return {'order_id':order_id,'members':payments,
                'total_new_due':money(sum(x['new_due'] for x in payments)),
                'requires_approval': True,
                'note':'Approval records a payable amount; it does not transfer funds. Members must independently verify their records.'}


def approve_settlement(order_id):
    with LOCK, connect() as c:
        require_order(c,order_id)
        payments=settlement_preview(order_id)
        if payments['total_new_due'] <= 0:
            raise ValueError('No new accepted work awaiting payout approval')
        for p in payments['members']:
            if p['new_due']:
                c.execute('UPDATE assignments SET approved_payout=approved_payout+? WHERE id=?',
                          (p['new_due'],p['assignment_id']))
        record(c,'payout_human_approved',{'order_id':order_id,'total':payments['total_new_due'],
                                        'financial_transfer':'NOT PERFORMED'})
        return {'message':'Payout ledger approved. No money transferred.','preview':payments}


def run_agent(order_id):
    with LOCK, connect() as c:
        o = require_order(c,order_id)
        output = agent_plan(o,assignment_rows(c,order_id),rows(c,'SELECT * FROM members'),workload_by_member(c))
        stored=[]
        for action in output['proposed_actions']:
            existing=one(c,'''SELECT id FROM agent_actions WHERE order_id=? AND action_type=?
                           AND status='proposed' ORDER BY id DESC LIMIT 1''',(order_id,action['type']))
            if existing:
                ident=existing['id']
            else:
                cur=c.execute('''INSERT INTO agent_actions (order_id,action_type,title,reason)
                                 VALUES (?,?,?,?)''',(order_id,action['type'],action['label'],action['reason']))
                ident=cur.lastrowid
            stored.append(ident)
        output['action_ids']=stored
        record(c,'agent_proposal_generated',{'order_id':order_id,'action_ids':stored,
                                            'external_actions_executed':0})
        return output


def approve_agent_action(action_id):
    """Perform a bounded, internal action after explicit human approval."""
    with LOCK, connect() as c:
        a=one(c,'SELECT * FROM agent_actions WHERE id=?',(int(action_id),))
        if not a:
            raise ValueError('Agent action not found')
        if a['status']!='proposed':
            raise ValueError('Action already approved')
        o=require_order(c,a['order_id'])
        kind=a['action_type']
        if kind in ('contact_members','collect_progress'):
            active=rows(c,'''SELECT a.*, m.name FROM assignments a JOIN members m ON m.id=a.member_id
                             WHERE a.order_id=? AND a.allocated_units > a.completed_units''',(o['id'],))
            for worker in active:
                text=(f"Namaste {worker['name']} ji. For {o['product']} (order #{o['id']}), "
                      f"your remaining work is {worker['allocated_units']-worker['completed_units']} pieces. "
                      f"Please share an expected completion update before {o['due_date']}. "
                      "This is a draft only; nothing has been sent.")
                c.execute('''INSERT INTO message_drafts (order_id,member_id,text) VALUES (?,?,?)''',
                          (o['id'],worker['member_id'],text))
            note=f'Created {len(active)} local, UNSENT member check-in drafts. No messages sent.'
        elif kind=='review_quote':
            q=quote(o)
            note=(f"Coordinator quote checklist: recorded unit cost ₹{q['unit_cost']}, "
                  f"target-price floor ₹{q['min_quote_for_target']}, buyer offer ₹{q['buyer_price']}. "
                  'Review with the group and buyer; no negotiation sent.')
        elif kind=='review_allocation':
            note='Requested a human allocation review. Open Orders & Quotes to approve; no work changed.'
        elif kind=='quality_review':
            note='Created a human quality-inspection review reminder; no work rejected automatically.'
        else:
            raise ValueError('Unsupported action')
        c.execute("UPDATE agent_actions SET status='approved_prepared',outcome=? WHERE id=?",(note,action_id))
        record(c,'agent_local_action_approved',{'action_id':action_id,'action_type':kind,
                                                'outcome':note,'external_messages_sent':0})
        return {'message':note,'action_id':action_id}


def set_consent(mid,consent):
    with LOCK, connect() as c:
        m=one(c,'SELECT * FROM members WHERE id=?',(mid,))
        if not m:
            raise ValueError('Worker not found')
        c.execute('UPDATE members SET consent=? WHERE id=?',(int(bool(consent)),mid))
        record(c,'member_demo_consent_changed',{'member_id':mid,'consent':bool(consent)})
        return {'message':'Consent updated for demo. Existing assignments unchanged.'}


def assistant_reply(data):
    question=str(data.get('question','')).strip()[:600]
    if not question:
        raise ValueError('Enter a question')
    s=state()
    order_id=int(data.get('order_id') or (s['orders'][0]['id'] if s['orders'] else 0))
    selected=next((o for o in s['orders'] if o['id']==order_id),None)
    if not selected:
        raise ValueError('Choose a valid order')
    context={k:selected[k] for k in ('product','quantity','due_date','completed_units','status','quote','alerts')}
    context['workers']=[{'name':a['member_name'],'allocated':a['allocated_units'],
                         'completed':a['completed_units'],'accepted':a['accepted_units']} for a in selected['assignments']]
    # Strictly local Ollama endpoint. This project never sends user data to a hosted AI API.
    model=os.getenv('OLLAMA_MODEL','llama3.2:3b')
    prompt=("You are an operations assistant for a women's SHG. Answer in short clear Hinglish "
            "unless user prefers something else. Base every number on data. Do not claim any "
            "payment was sent, avoid legal assurances, and clearly ask for human consent before actions. "
            "If data is missing say it. JSON snapshot: " + json.dumps(context,ensure_ascii=False)
            + "\nUser question: " + question)
    try:
        body=json.dumps({'model':model,'prompt':prompt,'stream':False,
                         'options':{'temperature':0.2,'num_predict':220}}).encode()
        req=Request('http://127.0.0.1:11434/api/generate',data=body,
                    headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=8) as r:
            answer=json.load(r).get('response','').strip()
        if answer:
            return {'answer':answer,'mode':f'Local Ollama language model ({model})',
                    'notice':'AI-generated explanation, based on snapshot data; verify before action.'}
    except (URLError,TimeoutError,ValueError,OSError):
        pass
    q=selected['quote']
    alerts='; '.join(a['title'] for a in selected['alerts'])
    answer=(f"{selected['product']}: {selected['completed_units']}/{selected['quantity']} pieces produced. "
            f"Buyer price ₹{q['buyer_price']}/unit, estimated cost ₹{q['unit_cost']}/unit, "
            f"margin {q['margin_pct']}%. Alerts: {alerts}. "
            "Suggested next step: review worker progress and obtain group approval before changes. "
            "For free-form generative AI, start Ollama locally with the chosen model.")
    return {'answer':answer,'mode':'Verified template from local rule engine — NOT an LLM',
            'notice':'No Ollama model was contacted successfully; this fallback is not generative AI.'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[http]', fmt % args)

    def send(self, code, obj, content_type='application/json; charset=utf-8'):
        payload=(json.dumps(obj,ensure_ascii=False).encode('utf-8') if not isinstance(obj,bytes) else obj)
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        u=urlparse(self.path)
        try:
            if u.path == '/api/state':
                return self.send(200,state())
            if u.path == '/api/health':
                return self.send(200,{'ok':True,'service':'DhaagaProof AI','local_only':HOST in ('127.0.0.1','localhost')})
            if u.path == '/api/plan':
                return self.send(200,preview_plan(int(parse_qs(u.query).get('order_id',['0'])[0])))
            if u.path == '/api/settlement':
                return self.send(200,settlement_preview(int(parse_qs(u.query).get('order_id',['0'])[0])))
            if u.path == '/api/export.csv':
                with connect() as c:
                    data=assignment_rows(c)
                stream=StringIO()
                writer=csv.writer(stream)
                writer.writerow(['Order','Member','Assigned','Produced','Accepted','Approved payout INR'])
                for a in data:
                    writer.writerow([a['product'],a['member_name'],a['allocated_units'],a['completed_units'],a['accepted_units'],a['approved_payout']])
                return self.send(200,stream.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
            name = 'index.html' if u.path in ('','/') else u.path.lstrip('/')
            candidate=(STATIC / name).resolve()
            if not candidate.is_relative_to(STATIC.resolve()) or not candidate.is_file():
                return self.send(404,{'error':'Not found'})
            mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
                  '.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.ico':'image/x-icon'}
            return self.send(200,candidate.read_bytes(),mime.get(candidate.suffix,'application/octet-stream'))
        except (ValueError,TypeError,KeyError) as e:
            return self.send(400,{'error':str(e)})
        except Exception as e:
            print('Unexpected GET error:',repr(e))
            return self.send(500,{'error':'Unexpected server error'})

    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if size < 1 or size > 65536:
            return self.send(413,{'error':'JSON body required; max 64 KB'})
        try:
            d=json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(d,dict):
                raise ValueError('Expected a JSON object')
            url=urlparse(self.path).path
            if url=='/api/orders': result=make_order(d)
            elif url=='/api/plan/approve': result=approve_plan(int(d['order_id']))
            elif url=='/api/progress': result=update_progress(d)
            elif url=='/api/settlement/approve': result=approve_settlement(int(d['order_id']))
            elif url=='/api/agent/run': result=run_agent(int(d['order_id']))
            elif url=='/api/agent/approve': result=approve_agent_action(int(d['action_id']))
            elif url=='/api/assistant': result=assistant_reply(d)
            elif url=='/api/consent': result=set_consent(int(d['member_id']),bool(d['consent']))
            else: return self.send(404,{'error':'Unknown endpoint'})
            return self.send(200,result)
        except (ValueError,TypeError,KeyError,OverflowError) as e:
            return self.send(400,{'error':str(e)})
        except Exception as e:
            print('Unexpected POST error:',repr(e))
            return self.send(500,{'error':'Unexpected server error'})


def main():
    init_db()
    http=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'\n  DHAAGAPROOF AI — offline-first working demo\n'
          f'  Open: http://{HOST}:{PORT}\n'
          f'  Demo data are fictional; payments are never transferred.\n'
          f'  Press Ctrl+C to stop.\n')
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
    finally:
        http.server_close()

if __name__=='__main__':
    main()
