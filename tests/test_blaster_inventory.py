"""Frozen whole-suite metadata is a roadmap denominator, not a new score."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('blaster_inventory', ROOT / 'scripts/inventory_blaster.py')
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class BlasterInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = inventory.load_inventory(ROOT)
        cls.rows = cls.catalog['declarations']
        cls.cases = [row for row in cls.rows if row['canonical_runner_member']]

    def test_denominator_follows_official_index_not_all_declarations(self):
        counts = {row['id']: row['canonical_case_count'] for row in self.catalog['families']}
        self.assertEqual(counts, {'NNG4':108,'STG4':52,'ITL4':44,'MiniF2F':96,'Verina':108,
                                 'UPLCWidth':6,'UPLCDepth':7,'BlasterHome':50,'SmtHome':50,
                                 'AutoHome':50,'AesopHome':50,'HammerHome':50})
        self.assertEqual(len(self.cases),671)
        self.assertEqual(len(self.rows),683)
        self.assertEqual(sum(row['source_kind']=='example' for row in self.rows),9)
        self.assertEqual(self.catalog['summary']['suite_lean_files'],375)
        self.assertEqual(self.catalog['summary']['lean_files'],378)
        self.assertEqual(len({row['canonical_case_id'] for row in self.cases}),671)
        self.assertIsNone(self.catalog['summary']['full_suite_score'])
        self.assertFalse(self.catalog['summary']['runnable_full_suite'])
        self.assertEqual(self.catalog['summary']['exact_header_duplicate_groups'],2)
        self.assertEqual(self.catalog['summary']['exact_header_duplicate_excess'],4)

    def test_every_target_binds_source_file_header_and_prefix(self):
        files={row['path']:row for row in self.catalog['files']}
        for row in self.cases:
            self.assertEqual(row['source_commit'],inventory.COMMIT)
            self.assertEqual(row['source_repository'],inventory.REPO)
            self.assertEqual(row['source_sha256'],files[row['source_path']]['sha256'])
            self.assertEqual(row['source_git_blob'],files[row['source_path']]['git_blob'])
            self.assertGreater(row['source_line'],0)
            self.assertEqual(inventory.sha(row['header'].encode()),row['header_sha256'])
            self.assertEqual(len(row['source_prefix_sha256']),64)
            identity={'header':row['header'],'source_path':row['source_path'],
                      'source_commit':inventory.COMMIT,'source_file_sha256':row['source_sha256'],
                      'source_prefix_sha256':row['source_prefix_sha256']}
            self.assertEqual(inventory.sha(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode()),
                             row['statement_identity_sha256'])
        required={'benchmarks/benchmark_config.sh','benchmarks/benchmark_core.sh','benchmarks/benchmark_utils.sh',
                  'latest/run_latest.sh','lakefile.lean','lake-manifest.json','lean-toolchain','LICENSE',
                  'BlasterBenchmarks/UPLC/generate.py'}
        self.assertTrue(required <= set(files))

    def test_two_upstream_helper_targets_are_blocked_without_spec_substitution(self):
        ambiguous=[row for row in self.cases if row['target_integrity']=='upstream_harness_targets_helper']
        self.assertEqual({row['source_name'] for row in ambiguous},{'eq_of_sub_zero_and_ge','check_correct'})
        self.assertEqual({row['intended_final_specification']['source_name'] for row in ambiguous},
                         {'arraySum_spec_satisfied','isPerfectSquare_spec_satisfied'})
        for row in ambiguous:
            self.assertEqual(row['integration_status'],'blocked')
            self.assertNotIn('pilot_mapping',row)
            intended=row['intended_final_specification']
            self.assertEqual(inventory.sha(intended['header'].encode()),intended['header_sha256'])
        later=[row for row in self.rows if row['source_kind']=='theorem' and not row['canonical_runner_member']]
        self.assertEqual(len(later),3)
        self.assertTrue(all(row['exclusion_reason']=='later_declaration_truncated_by_upstream_taskdir_proof_swap'
                            for row in later))

    def test_nng_contexts_cover_all_headers_without_importing_original_proofs(self):
        rows=[row for row in self.rows if row['family']=='NNG4']
        self.assertEqual(len(rows),117)
        dotted=[row for row in rows if (row['source_name'] or '').startswith('MyNat.')]
        self.assertEqual(len(dotted),3)
        for row in rows:
            statement={'context':row['context'],'header':row['header']}
            self.assertEqual(inventory.sha(json.dumps(statement,ensure_ascii=False,separators=(',',':')).encode()),
                             row['statement_sha256'])
            self.assertNotIn('sorry',row['header'])
            self.assertNotIn('native',row['header'])
            self.assertTrue(row['header'].endswith(':='))
        for row in dotted:
            self.assertEqual(row['full_name'],'BlasterBenchmarks.NNG4.'+row['source_name'])
        hard=next(row for row in rows if row['source_name']=='level10')
        self.assertIn('(n + 3)',hard['header'])
        self.assertEqual(hard['measurement_status'],'not_measured')
        self.assertTrue(hard['canonical_runner_member'])

    def test_pilot_twelve_have_exact_hash_bindings_others_are_unmeasured(self):
        manifest=json.loads((ROOT/inventory.PILOT_PATH).read_text())
        measured=[row for row in self.cases if 'pilot_mapping' in row]
        self.assertEqual(len(measured),12)
        for row in measured:
            binding=row['pilot_mapping']
            self.assertEqual(binding['manifest_sha256'],inventory.sha((ROOT/inventory.PILOT_PATH).read_bytes()))
            self.assertEqual(binding['lock_sha256'],inventory.sha((ROOT/inventory.PILOT_LOCK_PATH).read_bytes()))
            original=next(case for case in manifest['cases'] if case['id']==binding['case_id'])
            for key in ('context','header','statement_sha256','full_name'):
                self.assertEqual(row[key],original[key])
            self.assertEqual(row['source_sha256'],manifest['source']['sha256'])
            self.assertEqual(row['source_git_blob'],manifest['source']['git_blob'])
        remaining=[row for row in self.cases if 'pilot_mapping' not in row]
        self.assertEqual(len(remaining),659)
        self.assertTrue(all(row['measurement_status']=='not_measured' for row in remaining))
        self.assertTrue(self.catalog['summary']['not_measured_is_not_failure'])

    def test_checked_in_uplc_extra_depth_case_is_preserved(self):
        depth=[row for row in self.cases if row['family']=='UPLCDepth']
        self.assertEqual(len(depth),7)
        extra=next(row for row in depth if row['runner_goal_id']=='d_sum_16')
        self.assertIn('16',extra['header'])
        self.assertEqual(extra['measurement_status'],'not_measured')

    def test_lexer_ignores_nested_comments_strings_and_binder_assignments(self):
        source='''/- theorem fake : False := by sorry /- example : False := by sorry -/ -/
def text := "theorem invisible : False := by sorry"
-- lemma hidden : False := by sorry
theorem real (n : Nat := 2) : n = n := by rfl
example (P : Type) (p : P) : P := p
'''
        rows=inventory.declarations(source)
        self.assertEqual([row['source_name'] for row in rows],['real',None])
        self.assertEqual(rows[0]['header'],'theorem real (n : Nat := 2) : n = n :=')
        self.assertEqual(rows[1]['source_kind'],'example')

    def test_parser_fails_explicitly_on_unsupported_or_unterminated_input(self):
        with self.assertRaises(ValueError):inventory.mask_lean('/- unclosed')
        with self.assertRaises(ValueError):inventory.declarations('theorem missing : True\n')
        with self.assertRaises(ValueError):inventory.nng_contexts('axiom forbidden : False\n',[])

    def test_wrong_upstream_revision_is_rejected_before_inventory_reads(self):
        with patch.object(inventory.subprocess,'check_output',return_value='0'*40+'\n'):
            with self.assertRaisesRegex(ValueError,'immutable inventory commit'):
                inventory.build_inventory('unused',ROOT)

    def test_changed_checkout_config_is_rejected_against_pinned_git_blob(self):
        original=b'BENCHMARK_FILES=(original)\n'
        blob=hashlib.sha1(b'blob '+str(len(original)).encode()+b'\0'+original).hexdigest()
        tree=('100644 blob '+blob+'\tbenchmark_config.sh\0').encode()
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'benchmark_config.sh').write_text('BENCHMARK_FILES=(edited)\n')
            with patch.object(inventory.subprocess,'check_output',side_effect=[inventory.COMMIT+'\n',tree]):
                with self.assertRaisesRegex(ValueError,'Source bytes differ from pinned Git blob'):
                    inventory.build_inventory(directory,ROOT)

    def test_metadata_or_protected_input_drift_invalidates_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary=Path(directory)
            for path in [inventory.CATALOG_PATH,inventory.LOCK_PATH]+inventory.PROTECTED_PATHS:
                target=temporary/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/path).read_bytes())
            self.assertEqual(inventory.load_inventory(temporary)['id'],inventory.CATALOG_ID)
            changed=copy.deepcopy(self.catalog);changed['summary']['canonical_runner_slots']=12
            (temporary/inventory.CATALOG_PATH).write_text(json.dumps(changed))
            with self.assertRaises(ValueError):inventory.load_inventory(temporary)
            (temporary/inventory.CATALOG_PATH).write_bytes((ROOT/inventory.CATALOG_PATH).read_bytes())
            with (temporary/inventory.PILOT_PATH).open('a') as stream:stream.write(' ')
            with self.assertRaises(ValueError):inventory.load_inventory(temporary)

    def test_symlink_source_resources_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'actual').write_text('data');(root/'linked').symlink_to(root/'actual')
            with self.assertRaisesRegex(ValueError,'Symlink'):inventory.safe_file(root,'linked')


if __name__=='__main__':
    unittest.main()
