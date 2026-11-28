"""Bounded concurrent read leases over one authenticated identity per profile."""
import atexit
import contextvars
import hashlib
import json
import threading
import time
_stop=contextvars.ContextVar('nas_stop',default=lambda:False)
class Lease:
    def __init__(self,pool,key,entry,stop):self.pool,self.key,self.entry,self.stop,self.closed=pool,key,entry,stop,False
    def __getattr__(self,name):
        value=getattr(self.entry['client'],name)
        if not callable(value):return value
        def call(*args,**kwargs):
            if self.closed or self.stop():raise InterruptedError('Megszakítva')
            token=_stop.set(self.stop)
            try:return value(*args,**kwargs)
            finally:_stop.reset(token)
        return call
    def close(self):
        with self.pool.condition:
            if not self.closed:
                self.closed=True;self.entry['active']-=1;self.entry['used']=time.monotonic();self.pool.condition.notify_all()
class NasSessionPool:
    def __init__(self,limit=4,idle=300):self.limit,self.idle=limit,idle;self.entries={};self.condition=threading.Condition(threading.RLock());self.timer=None
    def acquire(self,credentials,stop,factory,session_name='FileStation'):
        stop=stop or (lambda:False)
        identity={k:credentials.get(k,'') for k in ('nas_local_url','nas_direct_url','quickconnect_id','nas_username','nas_password','nas_device_tokens')}
        key=hashlib.sha256(json.dumps([session_name,identity],sort_keys=True,default=str).encode()).hexdigest()
        self.reap()
        with self.condition:
            while key in self.entries and self.entries[key]['active']>=self.limit:
                if stop():raise InterruptedError('Megszakítva')
                self.condition.wait(.05)
            if stop():raise InterruptedError('Megszakítva')
            entry=self.entries.get(key)
            if entry is None:
                token=_stop.set(stop)
                try:client=factory(lambda:_stop.get()())
                finally:_stop.reset(token)
                entry={'client':client,'active':0,'used':time.monotonic()};self.entries[key]=entry
            entry['active']+=1
            if self.timer is None:
                self.timer=threading.Timer(min(60,self.idle),self._tick);self.timer.daemon=True;self.timer.start()
            return Lease(self,key,entry,stop)
    def _tick(self):
        with self.condition:self.timer=None
        self.reap()
        with self.condition:
            if self.entries and self.timer is None:
                self.timer=threading.Timer(min(60,self.idle),self._tick);self.timer.daemon=True;self.timer.start()
    def reap(self):
        old=[]
        with self.condition:
            for key,entry in list(self.entries.items()):
                if not entry['active'] and time.monotonic()-entry['used']>=self.idle:old.append(self.entries.pop(key)['client'])
        for client in old:
            try:client.close()
            except Exception as error:
                import logging
                logging.getLogger("SynoStream").warning("NAS idle cleanup failed: %s",type(error).__name__)
    def close(self):
        with self.condition:
            entries=list(self.entries.values());self.entries.clear()
            if self.timer:self.timer.cancel();self.timer=None
            self.condition.notify_all()
        for entry in entries:
            try:entry['client'].close()
            except Exception as error:
                import logging
                logging.getLogger('SynoStream').warning('NAS shutdown cleanup failed: %s',type(error).__name__)
pool=NasSessionPool()
atexit.register(pool.close)
