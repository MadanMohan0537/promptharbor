import unittest
from dataclasses import replace
from promptharbor.core import Bundle, Evidence, Registry, ReleaseManager, Sample

def bundle(): return Bundle("Be accurate", {"name":"demo","temperature":0}, {"top_k":3}, [{"name":"search","schema":{"q":"str"}}])

class TestPromptHarbor(unittest.TestCase):
    def test_digest_deterministic(self): self.assertEqual(bundle().digest, bundle().digest)
    def test_each_dependency_invalidates_evidence(self):
        b=bundle(); e=Evidence(b.digest,"suite",.9,10)
        changes=[replace(b,prompt="Changed"),replace(b,model={"name":"other"}),replace(b,retrieval={"top_k":9}),replace(b,tools=[])]
        self.assertTrue(e.validates(b,.8)); self.assertTrue(all(not e.validates(x,.8) for x in changes))
    def test_explicit_scope_ignores_unscoped_change(self):
        b=replace(bundle(), dependency_scope=("prompt",)); e=Evidence(b.digest,"suite",.9,10)
        self.assertTrue(e.validates(replace(b,model={"name":"new"}),.8))
    def test_bad_scope(self):
        with self.assertRaises(ValueError): replace(bundle(), dependency_scope=("unknown",))
    def test_semver_required(self):
        with self.assertRaises(ValueError): Registry().register("v1",bundle(),"a","why")
    def test_rationale_required(self):
        with self.assertRaises(ValueError): Registry().register("1.0.0",bundle(),"a","")
    def test_duplicate_rejected(self):
        r=Registry(); r.register("1.0.0",bundle(),"a","why")
        with self.assertRaises(ValueError): r.register("1.0.0",bundle(),"a","why")
    def test_author_cannot_approve(self):
        r=Registry(); r.register("1.0.0",bundle(),"a","why")
        with self.assertRaises(ValueError): r.approve("1.0.0","a")
    def test_promotion_requires_approval(self):
        r=Registry(); b=bundle(); r.register("1.0.0",b,"a","why"); r.attach_evidence("1.0.0",Evidence(b.digest,"s",.9,1))
        with self.assertRaises(ValueError): ReleaseManager(r).promote("1.0.0")
    def test_promotion_rejects_stale_evidence(self):
        r=Registry(); b=bundle(); r.register("1.0.0",b,"a","why"); r.attach_evidence("1.0.0",Evidence("stale","s",.9,1)); r.approve("1.0.0","b")
        with self.assertRaises(ValueError): ReleaseManager(r).promote("1.0.0")
    def test_promotion_rejects_low_score(self):
        r=Registry(); b=bundle(); r.register("1.0.0",b,"a","why"); r.attach_evidence("1.0.0",Evidence(b.digest,"s",.2,1)); r.approve("1.0.0","b")
        with self.assertRaises(ValueError): ReleaseManager(r).promote("1.0.0")
    def test_route_is_deterministic(self):
        r=Registry(); b=bundle(); r.register("1.0.0",b,"a","why"); r.attach_evidence("1.0.0",Evidence(b.digest,"s",.9,1)); r.approve("1.0.0","b"); m=ReleaseManager(r); m.stable="0.9.0"; m.promote("1.0.0")
        self.assertEqual(m.route("user-1"),m.route("user-1"))
    def test_rollback_on_drop(self):
        r=Registry(); b=bundle(); r.register("1.0.0",b,"a","why"); r.attach_evidence("1.0.0",Evidence(b.digest,"s",.9,1)); r.approve("1.0.0","b"); m=ReleaseManager(r); m.stable="0.9.0"; m.promote("1.0.0")
        self.assertTrue(m.observe([Sample("a","0.9.0",.9),Sample("b","1.0.0",.5)])); self.assertIsNone(m.candidate)
    def test_no_rollback_without_both_cohorts(self):
        r=Registry(); m=ReleaseManager(r); m.stable="a"; m.candidate="b"; self.assertFalse(m.observe([Sample("1","a",.9)]))
    def test_diff_names_versions(self):
        r=Registry(); r.register("1.0.0",bundle(),"a","why"); r.register("1.1.0",replace(bundle(),prompt="new"),"a","why")
        self.assertIn("--- 1.0.0",r.diff("1.0.0","1.1.0"))
    def test_audit_records_actions(self):
        r=Registry(); r.register("1.0.0",bundle(),"a","why"); self.assertEqual("registered",r.audit[0]["event"])

if __name__ == "__main__": unittest.main()
