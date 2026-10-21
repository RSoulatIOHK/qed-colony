"""Public strict-score projection; these fixture reports are never published."""

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from colony.benchmark_state import STRATEGIES, read_live_benchmark
from colony.store import Store


NOW = dt.datetime(2026, 10, 21, 12, tzinfo=dt.timezone.utc).timestamp()


def fixture_case(name, kind="positive"):
    header = "theorem %s : %s :=" % (name, "False" if kind == "negative" else "True")
    context = ["namespace FixtureBenchmark", "abbrev ℕ := Nat", "section Measured", "open Nat"]
    results = {}
    for strategy, body in STRATEGIES.items():
        source = ("import Colony.Tactic\nset_option maxHeartbeats 200000\n" + "\n".join(context) + "\n" +
                  header + " " + body + "\n#print axioms FixtureBenchmark." + name +
                  "\nend Measured\nend FixtureBenchmark\n")
        results[strategy] = {"status": "proof_failed" if kind == "negative" else "kernel_accepted",
            "wall_seconds": 0.125, "proof_body": body, "axioms": None if kind == "negative" else [],
            "generated_source": source, "generated_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "command": ["private-command", "/" + "Users/example/private/argument"]}
    return {"id": name, "source_name": name, "source_line": 1 if kind == "positive" else None,
            "source_url": "https://github.com/example/upstream/blob/" + "b" * 40 + "/Cases.lean#L1" if kind == "positive" else None,
            "header": header, "kind": kind,
            "statement_sha256": hashlib.sha256(json.dumps({"context": context, "header": header},
                ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
            "results": results}


def fixture_report():
    return {"schema": "colony.live_benchmark.v1", "run_id": "fixture-run", "source_revision": "a" * 40,
        "started_at": "2026-10-21T11:59:00Z", "completed_at": "2026-10-21T12:00:00Z", "valid": True,
        "suite": {"id": "fixture-source-order-sample", "case_count": 1,
                  "suite_sha256": "c" * 64, "manifest_sha256": "d" * 64, "lock_sha256": "e" * 64,
                  "selection": {"kind": "first_named_theorems", "count": 1, "policy": "Source order only."}},
        "protocol": {"imports": ["Colony.Tactic"], "proof_bodies": dict(STRATEGIES),
                     "timeout_seconds": 20, "max_heartbeats": 200000, "manual_steps": False, "extra_helpers": False},
        "assurance": {"label": "Lean elaboration kernel; no independent replay", "independent_replay": False},
        "summary": {key: {"valid": True, "proved": 1, "accepted_unvalidated": None, "total": 1,
                          "proof_failed": 0, "timeouts": 0, "errors": 0, "wall_seconds": 0.125} for key in STRATEGIES},
        "cases": [fixture_case("fixture_positive")],
        "controls": [fixture_case("fixture_witness", "nonvacuity"), fixture_case("fixture_invalid", "negative")],
        "baseline_comparability": {"blaster": {"state": "unavailable", "reason": "Toolchains differ; no matched comparison."}}}


def coverage_counts(total, attempted=0, certified=0, uncertified=0):
    return {"attempted": attempted, "certified": certified, "proof_failed": 0, "timeouts": 0,
            "errors": 0, "uncertified": uncertified, "unattempted": total - attempted}


def fixture_northstar(report_digest):
    families = []
    for index, total in enumerate([108, 100] + [46] * 9 + [49]):
        admitted, blocked = (12 if index == 0 else 0), (2 if index == 1 else 0)
        family = "NNG4" if index == 0 else "Verina" if index == 1 else "FixtureFamily%d" % index
        families.append({"id": family, "label": family, "source_url": "https://github.com/example/upstream/tree/" + "b" * 40 + "/" + family,
            "total_cases": total, "admitted_cases": admitted, "unadmitted_cases": total - admitted - blocked,
            "integration_blocked_cases": blocked, "current": coverage_counts(total, admitted, admitted), "historical": None})
    return {"schema": "colony.benchmark_northstar.v1",
        "catalog": {"id": "fixture-full-catalog", "sha256": "c" * 64, "lock_sha256": "d" * 64,
                    "repository": "https://github.com/example/upstream", "upstream_revision": "b" * 40,
                    "url": "https://github.com/example/repo/blob/main/benchmarks/catalog.json",
                    "upstream_url": "https://github.com/example/upstream/tree/" + "b" * 40,
                    "total_cases": 671, "family_count": 12},
        "status": {"state": "current", "stale": False, "target_revision": "a" * 40,
                   "measured_revision": "a" * 40, "observed_at": "2026-10-21T12:00:00Z",
                   "report_sha256": report_digest, "binding_valid": True, "controls_valid": True, "message": "Measured fixture only."},
        "totals": {"total_cases": 671, "admitted_cases": 12, "unadmitted_cases": 657, "integration_blocked_cases": 2},
        "current": coverage_counts(671, 12, 12), "historical": None, "families": families,
        "issues": [{"canonical_case_id": "fixture.ambiguous%d" % index, "family": "Verina", "kind": "ambiguous_helper_target",
                    "message": "The source runner and target name differ.", "source_url": "https://github.com/example/upstream/blob/" + "b" * 40 + "/Ambiguous.lean"} for index in (1, 2)],
        "next_admission": {"family": "NNG4", "canonical_cases": 108, "admitted_cases": 12, "remaining_cases": 96,
                           "status": "governance_required", "message": "Admission requires reviewed governance."}}


class BenchmarkStateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.directory = self.root / "benchmark"
        self.directory.mkdir()
        self.report = fixture_report()
        self.status = {"schema": "colony.live_benchmark_status.v1", "state": "ready", "stale": False,
                       "target_revision": "a" * 40, "latest_revision": "a" * 40,
                       "observed_at": "2026-10-21T12:00:00Z", "message": "Measured fixture only."}

    def write(self):
        (self.directory / "latest.json").write_text(json.dumps(self.report))
        (self.directory / "status.json").write_text(json.dumps(self.status))

    def read(self):
        return read_live_benchmark(self.directory, now=NOW)

    def test_missing_files_do_not_invent_counts_or_reuse_legacy_reports(self):
        store = Store(self.root / "state.db").initialize()
        store.record_benchmark({"name": "Legacy manual proof", "solved": 999, "total": 999})
        snapshot = store.snapshot()
        self.assertIsNone(snapshot["live_benchmark"]["report"])
        self.assertTrue(snapshot["live_benchmark"]["status"]["stale"])
        self.assertNotIn("summary", snapshot["live_benchmark"])
        self.assertEqual(len(snapshot["benchmarks"]), 1)
        self.assertIsNone(snapshot["live_benchmark"]["north_star"]["catalog"])
        self.assertNotIn("current", snapshot["live_benchmark"]["north_star"])

    def test_snapshot_projects_actual_report_without_commands_or_private_context(self):
        self.report["commands"] = [["private-command", str(self.root)]]
        self.report["private_context"] = str(self.root)
        self.write()
        with patch("colony.benchmark_state.time.time", return_value=NOW):
            value = Store(self.root / "state.db").initialize().snapshot()["live_benchmark"]
        self.assertFalse(value["status"]["stale"])
        self.assertEqual(value["report"]["summary"]["colony"]["proved"], 1)
        self.assertEqual(len(value["report"]["cases"]), 1)
        self.assertEqual(len(value["report"]["controls"]), 2)
        encoded = json.dumps(value)
        self.assertNotIn("private-command", encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("command", value["report"]["cases"][0]["results"]["colony"])
        self.assertIsNone(value["report"]["controls"][1]["results"]["colony"]["axioms"])

    def test_running_refresh_and_changed_target_preserve_old_report_as_stale(self):
        for changes in ({"state": "running", "stale": True}, {"target_revision": "f" * 40}):
            with self.subTest(changes=changes):
                self.status.update(changes)
                self.write()
                value = self.read()
                self.assertTrue(value["status"]["stale"])
                self.assertEqual(value["report"]["source_revision"], "a" * 40)

    def test_missing_stopped_or_future_runner_observation_never_claims_freshness(self):
        for observed in (None, "2026-10-21T11:00:00Z", "2026-10-21T12:01:00Z"):
            with self.subTest(observed=observed):
                self.status.pop("observed_at", None)
                if observed:
                    self.status["observed_at"] = observed
                self.write()
                value = self.read()
                self.assertTrue(value["status"]["stale"])
                self.assertIn("freshness_reason", value["status"])
                self.assertIsNotNone(value["report"])

    def test_missing_status_retains_only_historical_evidence(self):
        self.write()
        (self.directory / "status.json").unlink()
        value = self.read()
        self.assertTrue(value["status"]["stale"])
        self.assertIsNotNone(value["report"])

    def test_failed_controls_withhold_certified_score_but_preserve_raw_evidence(self):
        invalid = self.report["controls"][1]["results"]["colony"]
        invalid.update(status="kernel_accepted", axioms=[])
        self.report["summary"]["colony"].update(valid=False, proved=None, accepted_unvalidated=1)
        self.report["valid"] = False
        self.write()
        value = self.read()
        self.assertFalse(value["report"]["valid"])
        self.assertIsNone(value["report"]["summary"]["colony"]["proved"])
        self.assertEqual(value["report"]["summary"]["colony"]["accepted_unvalidated"], 1)
        self.assertEqual(value["report"]["controls"][1]["results"]["colony"]["status"], "kernel_accepted")

    def test_invalid_controls_cannot_be_reported_as_a_numeric_win(self):
        self.report["controls"][1]["results"]["colony"].update(status="kernel_accepted", axioms=[])
        self.write()
        self.assertIsNone(self.read()["report"])

    def test_manual_proof_body_cannot_be_a_strict_tactic_win(self):
        self.report["cases"][0]["results"]["colony"]["proof_body"] = "by exact True.intro"
        self.write()
        self.assertIsNone(self.read()["report"])
        self.assertEqual(self.read()["status"]["state"], "error")

    def test_coherently_hashed_manual_steps_comments_and_helpers_are_not_strict_wins(self):
        mutations = {
            "manual proof with tactic comment": lambda source, header: source.replace(
                header + " by colony\n", header + " by exact True.intro\n-- by colony\n"),
            "semicolon proof suffix": lambda source, header: source.replace(
                header + " by colony\n", header + " by colony; exact True.intro\n"),
            "changed statement": lambda source, header: source.replace(header, header.replace("True", "False")),
            "extra helper before target": lambda source, header: source.replace(
                header, "theorem hidden_helper : True := by exact True.intro\n" + header),
            "extra helper after target": lambda source, header: source + "theorem hidden_helper : True := by exact True.intro\n",
            "extra import": lambda source, header: source.replace("import Colony.Tactic\n", "import Colony.Tactic\nimport Mathlib\n"),
            "changed heartbeat budget": lambda source, header: source.replace("maxHeartbeats 200000", "maxHeartbeats 0"),
            "wrong axiom evidence target": lambda source, header: source.replace("#print axioms FixtureBenchmark.fixture_positive", "#print axioms FixtureBenchmark.fixture_witness"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                self.report = fixture_report()
                case = self.report["cases"][0]
                result = case["results"]["colony"]
                result["generated_source"] = mutate(result["generated_source"], case["header"])
                result["generated_source_sha256"] = hashlib.sha256(result["generated_source"].encode()).hexdigest()
                self.write()
                self.assertIsNone(self.read()["report"])

    def test_changed_public_header_cannot_reuse_original_statement_hash(self):
        case = self.report["cases"][0]
        old_header = case["header"]
        case["header"] = old_header.replace("True", "False")
        for result in case["results"].values():
            result["generated_source"] = result["generated_source"].replace(old_header, case["header"])
            result["generated_source_sha256"] = hashlib.sha256(result["generated_source"].encode()).hexdigest()
        self.write()
        self.assertIsNone(self.read()["report"])

    def test_helper_context_cannot_be_admitted_by_rehashing_the_statement(self):
        case = self.report["cases"][0]
        context = ["namespace FixtureBenchmark", "abbrev ℕ := Nat", "section Measured", "open Nat",
                   "theorem helper : True := by exact True.intro"]
        case["statement_sha256"] = hashlib.sha256(json.dumps({"context": context, "header": case["header"]},
            ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        for result in case["results"].values():
            result["generated_source"] = result["generated_source"].replace("open Nat\n", "open Nat\n" + context[-1] + "\n")
            result["generated_source_sha256"] = hashlib.sha256(result["generated_source"].encode()).hexdigest()
        self.write()
        self.assertIsNone(self.read()["report"])

    def test_control_cases_cannot_enter_the_scored_denominator(self):
        for location, kind in (("cases", "nonvacuity"), ("controls", "positive")):
            with self.subTest(location=location):
                self.report = fixture_report()
                self.report[location][0]["kind"] = kind
                self.write()
                self.assertIsNone(self.read()["report"])

    def test_score_counts_must_match_actual_positive_case_outcomes(self):
        self.report["summary"]["colony"]["proved"] = 2
        self.write()
        self.assertIsNone(self.read()["report"])

    def test_kernel_acceptance_requires_allowed_axiom_evidence(self):
        for axioms in (None, ["sorryAx"], ["Lean.ofReduceBool"]):
            with self.subTest(axioms=axioms):
                self.report["cases"][0]["results"]["colony"]["axioms"] = axioms
                self.write()
                self.assertIsNone(self.read()["report"])

    def test_unsafe_public_text_is_withheld_without_echoing_the_path(self):
        private = "/" + "Users/example/private/source.lean"
        self.report["cases"][0]["header"] = private
        self.write()
        value = self.read()
        self.assertIsNone(value["report"])
        self.assertNotIn(private, json.dumps(value))

    def test_source_hash_mismatch_and_unsupported_assurance_fail_closed(self):
        for key in ("source_hash", "independent_replay"):
            with self.subTest(key=key):
                self.report = fixture_report()
                if key == "source_hash":
                    self.report["cases"][0]["results"]["colony"]["generated_source_sha256"] = "0" * 64
                else:
                    self.report["assurance"]["independent_replay"] = True
                self.write()
                self.assertIsNone(self.read()["report"])

    def test_oversize_malformed_and_nonfinite_inputs_fail_closed(self):
        self.write()
        with patch("colony.benchmark_state.MAX_REPORT_BYTES", 100):
            self.assertIsNone(self.read()["report"])
        for payload in ("{bad", '{"schema":"colony.live_benchmark.v1","x":NaN}'):
            (self.directory / "latest.json").write_text(payload)
            self.assertIsNone(self.read()["report"])

    def test_symlinked_report_does_not_expose_an_external_file(self):
        self.write()
        external = self.root / "external.json"
        external.write_text(json.dumps(self.report))
        (self.directory / "latest.json").unlink()
        (self.directory / "latest.json").symlink_to(external)
        self.assertIsNone(self.read()["report"])

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the DOM contract regression")
    def test_render_handles_null_axioms_invalid_scores_and_saved_snapshots(self):
        self.report["controls"][1]["results"]["colony"].update(status="timeout")
        self.report["summary"]["colony"].update(valid=False, proved=None, accepted_unvalidated=1)
        self.report["valid"] = False
        self.write()
        payload = self.read()
        script = r"""
const fs = require('fs'), vm = require('vm');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag, text='') { this.tag=tag; this.text=String(text); this.children=[]; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=[...children]; this.text=''; }
  get textContent() { return this.text + ' ' + this.children.map(n=>n.textContent??String(n)).join(' '); }
}
const container = new Node('section');
const el=(tag, cls='', text='')=>new Node(tag,text);
const state={source:'live',data:{live_benchmark:payload,project:{repo_url:'https://github.com/example/repo'}}};
const context={state,el,$:()=>container,pretty:x=>String(x).replaceAll('_',' '),
  dateTime:x=>x,relative:x=>'recorded time',link:(label,url)=>url?new Node('a',label):null,
  empty:(title,message)=>new Node('p',title+' '+message)};
vm.createContext(context);
const source=fs.readFileSync('observatory/dist/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('  const liveStrategies ='),source.indexOf('  function renderBenchmarks()')),context);
vm.runInContext('renderLiveBenchmark()',context);
const live=container.textContent;
state.source='snapshot'; vm.runInContext('renderLiveBenchmark()',context);
const saved=container.textContent;
state.data.live_benchmark={status:{state:'unavailable',stale:true},report:null};
vm.runInContext('renderLiveBenchmark()',context);
process.stdout.write(JSON.stringify({live,saved,empty:container.textContent}));
"""
        completed = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(payload),
                                   capture_output=True, text=True, check=True, timeout=10,
                                   cwd=Path(__file__).resolve().parents[1])
        rendered = json.loads(completed.stdout)
        self.assertIn("no axiom evidence produced", rendered["live"])
        self.assertIn("Not certified", rendered["live"])
        self.assertNotIn("null /", rendered["live"])
        self.assertIn("stale run", rendered["saved"])
        self.assertIn("No completed strict benchmark report", rendered["empty"])


class NorthStarStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.report = fixture_report()
        self.report["cases"] = [fixture_case("fixture_case%d" % index) for index in range(12)]
        self.report["suite"].update(case_count=12)
        self.report["suite"]["selection"]["count"] = 12
        for item in self.report["summary"].values():
            item.update(proved=12, total=12, wall_seconds=1.5)
        self.status = {"schema": "colony.live_benchmark_status.v1", "state": "ready", "stale": False,
            "target_revision": "a" * 40, "latest_revision": "a" * 40, "observed_at": "2026-10-21T12:00:00Z"}
        self.write_report()
        self.north = fixture_northstar(self.digest)
        self.write_north()

    def write_report(self):
        raw = json.dumps(self.report).encode()
        (self.directory / "latest.json").write_bytes(raw)
        (self.directory / "status.json").write_text(json.dumps(self.status))
        self.digest = hashlib.sha256(raw).hexdigest()

    def write_north(self):
        (self.directory / "northstar.json").write_text(json.dumps(self.north))

    def read(self, now=NOW):
        return read_live_benchmark(self.directory, now=now)

    def test_whole_canonical_denominator_families_and_blocked_subset_are_separate(self):
        north = self.read()["north_star"]
        self.assertTrue(north["coverage_available"])
        self.assertEqual(north["catalog"]["total_cases"], 671)
        self.assertEqual(len(north["families"]), 12)
        self.assertEqual(north["current"], coverage_counts(671, 12, 12))
        self.assertEqual(north["totals"], {"total_cases": 671, "admitted_cases": 12, "unadmitted_cases": 657, "integration_blocked_cases": 2})
        self.assertEqual(north["current"]["proof_failed"], 0)
        self.assertEqual(north["current"]["unattempted"], 659)
        self.assertEqual(north["families"][0]["current"], coverage_counts(108, 12, 12))
        self.assertEqual(len(north["issues"]), 2)
        self.assertIsNone(north["historical"])

    def test_revision_change_preserves_history_without_combining_it_with_current(self):
        self.status.update(target_revision="f" * 40, stale=True)
        self.write_report()
        self.north["status"].update(target_revision="f" * 40, stale=True, state="historical")
        self.north["historical"] = {"measured_revision": "a" * 40, "counts": self.north["current"]}
        self.north["current"] = coverage_counts(671)
        for family in self.north["families"]:
            family["historical"], family["current"] = family["current"], coverage_counts(family["total_cases"])
        self.write_north()
        north = self.read()["north_star"]
        self.assertEqual(north["status"]["state"], "historical")
        self.assertEqual(north["current"]["attempted"], 0)
        self.assertEqual(north["historical"]["counts"]["certified"], 12)
        self.assertEqual(north["families"][0]["current"]["certified"], 0)
        self.assertEqual(north["families"][0]["historical"]["certified"], 12)

    def test_expired_runner_observation_moves_proofs_to_history(self):
        north = self.read(now=NOW + 301)["north_star"]
        self.assertEqual(north["status"]["state"], "historical")
        self.assertTrue(north["status"]["stale"])
        self.assertEqual(north["current"]["attempted"], 0)
        self.assertEqual(north["historical"]["counts"]["attempted"], 12)

    def test_exact_report_bytes_and_binding_are_required_for_coverage(self):
        for changes in ({"report_sha256": "0" * 64}, {"binding_valid": False}, {"measured_revision": "f" * 40}, {"report_sha256": None}):
            with self.subTest(changes=changes):
                self.north = fixture_northstar(self.digest)
                self.north["status"].update(changes)
                self.write_north()
                north = self.read()["north_star"]
                self.assertFalse(north["coverage_available"])
                self.assertEqual(north["current"]["certified"], 0)
                self.assertIsNone(north["historical"])
                self.assertEqual(north["status"]["state"], "unavailable")
        self.north = fixture_northstar(self.digest)
        self.write_north()
        with (self.directory / "latest.json").open("ab") as stream:
            stream.write(b"\n")
        self.assertFalse(self.read()["north_star"]["coverage_available"])

    def test_invalid_controls_never_produce_certified_catalog_cases(self):
        self.report["controls"][1]["results"]["colony"].update(status="kernel_accepted", axioms=[])
        self.report["summary"]["colony"].update(valid=False, proved=None, accepted_unvalidated=12)
        self.report["valid"] = False
        self.write_report()
        self.north = fixture_northstar(self.digest)
        self.north["status"].update(controls_valid=False, state="uncertified")
        self.north["current"] = coverage_counts(671, 12, 0, 12)
        self.north["families"][0]["current"] = coverage_counts(108, 12, 0, 12)
        self.write_north()
        north = self.read()["north_star"]
        self.assertTrue(north["coverage_available"])
        self.assertEqual(north["status"]["state"], "uncertified")
        self.assertEqual(north["current"]["certified"], 0)
        self.assertEqual(north["current"]["uncertified"], 12)
        self.north["current"] = coverage_counts(671, 12, 12)
        self.north["families"][0]["current"] = coverage_counts(108, 12, 12)
        self.write_north()
        self.assertIsNone(self.read()["north_star"]["catalog"])

    def test_inconsistent_or_fabricated_counts_are_withheld(self):
        for mutate in (
                lambda value: value["current"].update(attempted=671),
                lambda value: value["families"][0]["current"].update(certified=13),
                lambda value: value["totals"].update(unadmitted_cases=659),
                lambda value: value["families"][1].update(integration_blocked_cases=0),
                lambda value: value["status"].update(controls_valid=False),
                lambda value: value["next_admission"].update(remaining_cases=97)):
            with self.subTest(mutation=mutate):
                self.north = fixture_northstar(self.digest)
                mutate(self.north)
                self.write_north()
                state = self.read()
                self.assertIsNone(state["north_star"]["catalog"])
                self.assertIsNotNone(state["report"])

    def test_missing_unsafe_oversize_and_symlink_catalog_state_never_invent_coverage(self):
        self.north["private_log"] = "/" + "Users/example/private/local.log"
        self.write_north()
        self.assertNotIn("private_log", self.read()["north_star"])
        self.north["issues"][0]["message"] = self.north["private_log"]
        self.write_north()
        self.assertIsNone(self.read()["north_star"]["catalog"])
        self.north = fixture_northstar(self.digest)
        self.write_north()
        with patch("colony.benchmark_state.MAX_NORTHSTAR_BYTES", 100):
            self.assertIsNone(self.read()["north_star"]["catalog"])
        external = self.directory / "external.json"
        external.write_text(json.dumps(self.north))
        (self.directory / "northstar.json").unlink()
        (self.directory / "northstar.json").symlink_to(external)
        self.assertIsNone(self.read()["north_star"]["catalog"])
        (self.directory / "northstar.json").unlink()
        value = self.read()["north_star"]
        self.assertIsNone(value["catalog"])
        self.assertNotIn("current", value)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the DOM contract regression")
    def test_dom_shows_whole_denominator_only_twelve_families_and_saved_evidence_separately(self):
        script = r"""
const fs=require('fs'),vm=require('vm'),payload=JSON.parse(fs.readFileSync(0,'utf8'));
class Node{constructor(tag,text=''){this.tag=tag;this.text=String(text);this.children=[];}
append(...children){this.children.push(...children);}replaceChildren(...children){this.children=[...children];this.text='';}
get textContent(){return this.text+' '+this.children.map(n=>n.textContent??String(n)).join(' ');}}
const container=new Node('section'),state={source:'live',data:{live_benchmark:payload}};
const context={state,el:(tag,cls='',text='')=>new Node(tag,text),$:()=>container,
pretty:x=>String(x).replaceAll('_',' '),dateTime:x=>x,relative:x=>'recorded time',
link:(label,url)=>url?new Node('a',label):null,empty:(title,message)=>new Node('p',title+' '+message)};
vm.createContext(context);const source=fs.readFileSync('observatory/dist/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('  const liveStrategies ='),source.indexOf('  function renderBenchmarks()')),context);
vm.runInContext('renderNorthStar()',context);const live=container.textContent;
const find=n=>n.tag==='tbody'?n.children.length:n.children.reduce((sum,c)=>sum+find(c),0);
const familyRows=find(container);state.source='snapshot';vm.runInContext('renderNorthStar()',context);const saved=container.textContent;
state.data.live_benchmark={};vm.runInContext('renderNorthStar()',context);
process.stdout.write(JSON.stringify({live,saved,familyRows,empty:container.textContent}));
"""
        completed = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(self.read()),
            capture_output=True, text=True, check=True, timeout=10, cwd=Path(__file__).resolve().parents[1])
        rendered = json.loads(completed.stdout)
        for text in ("671 canonical source cases", "12 / 671", "659", "12 / 108", "2 upstream source ambiguities", "not failures", "whole canonical catalog JSON"):
            self.assertIn(text, rendered["live"])
        self.assertEqual(rendered["familyRows"], 12)
        self.assertIn("Saved coverage", rendered["saved"])
        self.assertIn("Historical measured coverage", rendered["saved"])
        self.assertIn("no live current-target coverage", rendered["saved"])
        self.assertIn("Full benchmark coverage unavailable", rendered["empty"])
        self.assertNotIn("671", rendered["empty"])


if __name__ == "__main__":
    unittest.main()
